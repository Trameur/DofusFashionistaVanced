/* Character preview: stacks baked skin parts on a canvas using the pose the
   server sends. Drag to turn, idle animation loops. */
(function (global) {
    'use strict';

    var TURN = ['0', '1', '2', '3', '4', '5', '6', '7'];
    // The client ships five orientations. mirror(d) = (4 - d) mod 8, so 2 and 6
    // are their own mirror.
    var MIRROR_OF = { '3': '1', '4': '0', '7': '5' };
    var PAD = 2;

    function mirrored(frame) {
        return frame.map(function (r) {
            return { order: r.order, node: r.node,
                     m: [-r.m[0], -r.m[1], -r.m[2], r.m[3], r.m[4], r.m[5]] };
        });
    }

    function CharacterPreview(canvas, options) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.base = options.assetBase.replace(/\/$/, '');
        this.look = options.look;
        this.colors = options.colors || {};
        this.origin = options.origin || [canvas.width / 2, canvas.height * 0.82];
        this.scale = (options.scale || 1) * (this.look.scale || 1);
        this.orientation = options.orientation || '1';
        this.order = TURN;
        this.frame = 0;
        this.images = {};
        this.manifests = {};
        this.poses = null;
        this.tintCanvas = document.createElement('canvas');
        this.tintCtx = this.tintCanvas.getContext('2d');
        this.skins = this.skinList();
    }

    CharacterPreview.prototype.skinList = function () {
        var ids = [this.look.body, this.look.head];
        for (var node in this.look.gear) {
            ids.push(this.look.gear[node]);
        }
        return ids.filter(function (id) { return !!id; });
    };

    CharacterPreview.prototype.load = function () {
        var self = this;
        var jobs = [fetch(this.base + '/poses/' + this.look.bones + '.json')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                for (var o in data.orientations) {
                    var kept = data.orientations[o].filter(function (f) { return f.length; });
                    data.orientations[o] = kept.length ? kept : data.orientations[o].slice(0, 1);
                }
                for (var target in MIRROR_OF) {
                    var from = data.orientations[MIRROR_OF[target]];
                    if (from && !data.orientations[target]) {
                        data.orientations[target] = from.map(mirrored);
                    }
                }
                self.poses = data;
                self.order = TURN.filter(function (d) { return data.orientations[d]; });
            })];
        // One missing piece must not cost the whole character, so a part that
        // fails to load is simply not drawn.
        this.skins.forEach(function (id) {
            jobs.push(fetch(self.base + '/parts/' + id + '/parts.json')
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) { if (data) { self.manifests[id] = data; } })
                .catch(function () {}));
        });
        return Promise.all(jobs).then(function () {
            if (!self.poses || !self.manifests[self.look.body]) {
                throw new Error('no character art');
            }
            return self;
        });
    };

    CharacterPreview.prototype.image = function (skinId, part) {
        var key = skinId + '/' + part;
        if (!this.images[key]) {
            var img = new Image();
            img.src = this.base + '/parts/' + skinId + '/' + encodeURIComponent(part) + '.png';
            this.images[key] = img;
        }
        return this.images[key];
    };

    CharacterPreview.prototype.entriesFor = function (node) {
        var out = [];
        var lower = node.toLowerCase();
        for (var i = 0; i < this.skins.length; i++) {
            var id = this.skins[i];
            var manifest = this.manifests[id];
            if (!manifest) { continue; }
            if (manifest[node]) { out.push({ skin: id, part: node, slot: null }); }
            for (var part in manifest) {
                var m = /^ColorGray_(\d+)_(.+)$/.exec(part);
                if (m && m[2].toLowerCase() === lower) {
                    out.push({ skin: id, part: part, slot: parseInt(m[1], 10) });
                }
            }
        }
        return out;
    };

    // A head ships every expression and a dozen spare skull shapes; drawing
    // them all at once turns the face into mush.
    var EXPRESSION = /^visage_(?!neutre|base)|_visage_(?!neutre)|^tete\d+$/;

    CharacterPreview.prototype.headEntries = function () {
        var manifest = this.manifests[this.look.head] || {};
        var suffix = '_' + (MIRROR_OF[this.orientation] || this.orientation);
        var out = [];
        for (var part in manifest) {
            if (part.indexOf(suffix, part.length - suffix.length) === -1) { continue; }
            var bare = part.replace(/^ColorGray_\d+_/, '').replace(/_\d+$/, '').toLowerCase();
            if (EXPRESSION.test(bare)) { continue; }
            var m = /^ColorGray_(\d+)_/.exec(part);
            out.push({ skin: this.look.head, part: part, slot: m ? parseInt(m[1], 10) : null });
        }
        return out;
    };

    CharacterPreview.prototype.tinted = function (img, rgb) {
        var c = this.tintCanvas, ctx = this.tintCtx;
        c.width = img.naturalWidth;
        c.height = img.naturalHeight;
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.drawImage(img, 0, 0);
        ctx.globalCompositeOperation = 'multiply';
        ctx.fillStyle = 'rgb(' + rgb.join(',') + ')';
        ctx.fillRect(0, 0, c.width, c.height);
        ctx.globalCompositeOperation = 'destination-in';
        ctx.drawImage(img, 0, 0);
        ctx.globalCompositeOperation = 'source-over';
        return c;
    };

    CharacterPreview.prototype.draw = function () {
        var ctx = this.ctx;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (!this.poses) { return; }
        var frames = this.poses.orientations[this.orientation];
        if (!frames || !frames.length) { return; }
        var nodes = frames[this.frame % frames.length];
        for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i];
            var list = node.node.indexOf('Tete') === 0
                ? this.headEntries() : this.entriesFor(node.node);
            for (var j = 0; j < list.length; j++) {
                this.drawPart(node, list[j]);
            }
        }
        ctx.setTransform(1, 0, 0, 1, 0, 0);
    };

    CharacterPreview.prototype.drawPart = function (node, entry) {
        var bounds = this.manifests[entry.skin][entry.part];
        var img = this.image(entry.skin, entry.part);
        if (!bounds || !img.complete || !img.naturalWidth) { return; }
        var rx = node.m[0], ux = node.m[1], tx = node.m[2];
        var ry = node.m[3], uy = node.m[4], ty = node.m[5];
        var ppu = bounds.ppu;
        var ox = bounds.x - PAD / ppu;
        var oy = bounds.y + PAD / ppu;
        var s = this.scale;
        this.ctx.setTransform(
            s * rx / ppu, -s * ry / ppu, -s * ux / ppu, s * uy / ppu,
            s * (rx * ox + ux * oy + tx) + this.origin[0],
            -s * (ry * ox + uy * oy + ty) + this.origin[1]);
        var rgb = entry.slot ? this.colors[entry.slot] : null;
        this.ctx.drawImage(rgb ? this.tinted(img, rgb) : img, 0, 0);
    };

    CharacterPreview.prototype.start = function () {
        var self = this, last = 0;
        function tick(now) {
            var frames = self.poses && self.poses.orientations[self.orientation];
            if (frames && frames.length > 1 && now - last > 1000 / 12) {
                self.frame++;
                last = now;
            }
            self.draw();
            self.raf = requestAnimationFrame(tick);
        }
        this.draw();
        this.raf = requestAnimationFrame(tick);
        this.bindDrag();
        return this;
    };

    CharacterPreview.prototype.stop = function () {
        if (this.raf) { cancelAnimationFrame(this.raf); }
    };

    CharacterPreview.prototype.at = function (index) {
        var n = this.order.length;
        return this.order[((index % n) + n) % n];
    };

    CharacterPreview.prototype.turn = function (step) {
        this.orientation = this.at(this.order.indexOf(this.orientation) + step);
        this.frame = 0;
    };

    CharacterPreview.prototype.bindDrag = function () {
        var self = this, dragging = false, startX = 0, startIndex = 0;
        this.canvas.addEventListener('pointerdown', function (e) {
            dragging = true;
            startX = e.clientX;
            startIndex = self.order.indexOf(self.orientation);
            self.canvas.setPointerCapture(e.pointerId);
        });
        this.canvas.addEventListener('pointermove', function (e) {
            if (!dragging) { return; }
            var next = self.at(startIndex + Math.round((e.clientX - startX) / 40));
            if (next !== self.orientation) {
                self.orientation = next;
                self.frame = 0;
            }
        });
        this.canvas.addEventListener('pointerup', function () { dragging = false; });
        this.canvas.addEventListener('pointercancel', function () { dragging = false; });
    };

    global.CharacterPreview = CharacterPreview;
}(window));
