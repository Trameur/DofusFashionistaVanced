/* Character preview: stacks baked skin parts on a canvas using the pose the
   server sends. Drag to turn, idle animation loops. */
(function (global) {
    'use strict';

    var TURN = ['0', '1', '2', '3', '4', '5', '6', '7'];
    // mirror(d) = (4 - d) mod 8; the client ships five orientations.
    var MIRROR_OF = { '3': '1', '4': '0', '7': '5' };
    var PAD = 2;

    function mirrored(frame) {
        return frame.map(function (r) {
            var out = {};
            for (var key in r) { out[key] = r[key]; }
            out.m = [-r.m[0], -r.m[1], -r.m[2], r.m[3], r.m[4], r.m[5]];
            return out;
        });
    }

    function fillMirrors(orientations, mirror) {
        for (var target in MIRROR_OF) {
            var from = orientations[MIRROR_OF[target]];
            if (from && !orientations[target]) {
                orientations[target] = mirror(from);
            }
        }
    }

    // a then b, both [rx, ux, tx, ry, uy, ty].
    function compose(a, b) {
        return [a[0] * b[0] + a[1] * b[3],
                a[0] * b[1] + a[1] * b[4],
                a[0] * b[2] + a[1] * b[5] + a[2],
                a[3] * b[0] + a[4] * b[3],
                a[3] * b[1] + a[4] * b[4],
                a[3] * b[2] + a[4] * b[5] + a[5]];
    }

    function scaledBy(k, m) {
        return [k * m[0], k * m[1], k * m[2], k * m[3], k * m[4], k * m[5]];
    }

    function mountColors(mount) {
        var out = {};
        var list = (mount && mount.colors) || [];
        for (var i = 0; i < list.length; i++) {
            out[i + 1] = [parseInt(list[i].substr(0, 2), 16),
                          parseInt(list[i].substr(2, 2), 16),
                          parseInt(list[i].substr(4, 2), 16)];
        }
        return out;
    }

    function CharacterPreview(canvas, options) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.base = options.assetBase.replace(/\/$/, '');
        // Pieces are id-addressed and cached a year; only the url can bust it.
        this.stamp = options.assetVersion
            ? '?v=' + encodeURIComponent(options.assetVersion) : '';
        // The cache file names carry the format version. Asking for that name
        // is what lets the front end answer from disk without a worker.
        this.formats = options.assetFormats || {};
        this.look = options.look;
        this.colors = options.colors || {};
        // The template ships a backing store twice the css size, which a phone
        // at 3x then upscales. Follow the screen instead, never below the two
        // it already had, and carry the ratio in the draw scale since paint()
        // replaces the transform.
        var cssWidth = canvas.clientWidth || canvas.width / 2;
        var cssHeight = canvas.clientHeight || canvas.height / 2;
        var ratio = Math.min(Math.max(window.devicePixelRatio || 1, 2), 3);
        canvas.width = Math.round(cssWidth * ratio);
        canvas.height = Math.round(cssHeight * ratio);
        this.origin = options.origin || [canvas.width / 2, canvas.height * 0.82];
        this.baseScale = (options.scale || 1) * ratio / 2;
        this.scale = this.baseScale * (this.look.scale || 1);
        this.orientation = options.orientation || '1';
        this.order = TURN;
        this.frame = 0;
        this.images = {};
        this.manifests = {};
        this.poses = null;
        this.mount = null;
        this.mountColors = mountColors(this.look.mount);
        this.tintCanvas = document.createElement('canvas');
        this.tintCtx = this.tintCanvas.getContext('2d');
        this.skins = this.skinList();
    }

    CharacterPreview.prototype.suffix = function (kind) {
        var n = this.formats[kind];
        return n ? '-v' + n : '';
    };

    CharacterPreview.prototype.skinList = function () {
        var ids = [this.look.body, this.look.head];
        for (var node in this.look.gear) {
            ids.push(this.look.gear[node]);
        }
        return ids.filter(function (id) { return !!id; });
    };

    CharacterPreview.prototype.load = function () {
        var self = this;
        var jobs = [fetch(this.base + '/poses/' + this.look.bones
                + this.suffix('pose') + '.json' + this.stamp)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                for (var o in data.orientations) {
                    var kept = data.orientations[o].filter(function (f) { return f.length; });
                    data.orientations[o] = kept.length ? kept : data.orientations[o].slice(0, 1);
                }
                fillMirrors(data.orientations, function (frames) {
                    return frames.map(mirrored);
                });
                self.poses = data;
                self.order = TURN.filter(function (d) { return data.orientations[d]; });
            })];
        if (this.look.mount) {
            jobs.push(fetch(this.base + '/mount/' + this.look.mount.bone
                    + '/parts' + this.suffix('mount') + '.json' + this.stamp)
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    if (!data) { return; }
                    fillMirrors(data.orientations, mirrored);
                    self.mount = data;
                })
                .catch(function () {}));
        }
        // A part that fails to load is skipped, not fatal.
        this.skins.forEach(function (id) {
            jobs.push(fetch(self.base + '/parts/' + id + '/parts'
                    + self.suffix('skin') + '.json' + self.stamp)
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    if (!data) { return; }
                    self.manifests[id] = data;
                    return self.decoded(id);
                })
                .catch(function () {}));
        });
        return Promise.all(jobs).then(function () {
            if (!self.poses || !self.manifests[self.look.body]) {
                throw new Error('no character art');
            }
            // A rider without its mount is a legless torso.
            if (self.look.mount && !self.mount) {
                throw new Error('no mount art');
            }
            return self;
        });
    };

    CharacterPreview.prototype.image = function (skinId) {
        if (!this.images[skinId]) {
            var img = new Image();
            img.src = this.base + '/parts/' + skinId + '/atlas.webp' + this.stamp;
            this.images[skinId] = img;
        }
        return this.images[skinId];
    };

    // The head is drawn whole at the Tete node, in its own local space. Some
    // heads carry pieces named after other skeleton nodes (Chapeau, Natte,
    // Cole), and entriesFor used to match those too, painting them a second
    // time at that node, offset and oversized: on an Eliotrope the braid came
    // back tinted by slot 5, a blue slab beside the head. Only skip the ones
    // headEntries already draws for the orientation on screen, or a Sram
    // loses the collar its own node carries.
    CharacterPreview.prototype.headDrawn = function () {
        if (this.headDrawnFor !== this.orientation) {
            var seen = {};
            var list = this.headEntries();
            for (var i = 0; i < list.length; i++) { seen[list[i].part] = true; }
            this.headDrawnParts = seen;
            this.headDrawnFor = this.orientation;
        }
        return this.headDrawnParts;
    };

    CharacterPreview.prototype.entriesFor = function (node) {
        var out = [];
        var lower = node.toLowerCase();
        var drawn = this.headDrawn();
        for (var i = 0; i < this.skins.length; i++) {
            var id = this.skins[i];
            var manifest = this.manifests[id];
            var isHead = id === this.look.head;
            if (!manifest) { continue; }
            if (manifest[node] && !(isHead && drawn[node])) {
                out.push({ skin: id, part: node, slot: null });
            }
            for (var part in manifest) {
                if (isHead && drawn[part]) { continue; }
                var m = /^ColorGray_(\d+)_(.+)$/.exec(part);
                if (m && m[2].toLowerCase() === lower) {
                    out.push({ skin: id, part: part, slot: parseInt(m[1], 10) });
                }
            }
        }
        return out;
    };

    // Heads ship every expression; drawing them all turns the face to mush.
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

    CharacterPreview.prototype.tinted = function (img, rgb, sx, sy, w, h) {
        var c = this.tintCanvas, ctx = this.tintCtx;
        c.width = w;
        c.height = h;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(img, sx, sy, w, h, 0, 0, w, h);
        ctx.globalCompositeOperation = 'multiply';
        ctx.fillStyle = 'rgb(' + rgb.join(',') + ')';
        ctx.fillRect(0, 0, w, h);
        // The greyscale art sits at a median luminance of 87/255, so a plain
        // multiply returned about a third of the chosen colour. Mid grey is
        // the neutral point the art is drawn around, not white.
        ctx.globalCompositeOperation = 'lighter';
        ctx.drawImage(c, 0, 0);
        ctx.globalCompositeOperation = 'destination-in';
        ctx.drawImage(img, sx, sy, w, h, 0, 0, w, h);
        ctx.globalCompositeOperation = 'source-over';
        return c;
    };

    // The first draw waits for the whole sheet, so the character appears at
    // once instead of a piece at a time.
    CharacterPreview.prototype.decoded = function (skinId) {
        var img = this.image(skinId);
        if (img.complete && img.naturalWidth) { return null; }
        return img.decode ? img.decode().catch(function () {})
            : new Promise(function (done) {
                img.onload = img.onerror = function () { done(); };
            });
    };

    CharacterPreview.prototype.mountImage = function (part) {
        var bone = this.look.mount.bone;
        var key = 'mount/' + bone + '/' + part;
        if (!this.images[key]) {
            var img = new Image();
            img.src = this.base + '/mount/' + bone + '/' + part + '.png' + this.stamp;
            this.images[key] = img;
        }
        return this.images[key];
    };

    CharacterPreview.prototype.draw = function () {
        var ctx = this.ctx;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (!this.poses) { return; }
        var frames = this.poses.orientations[this.orientation];
        if (!frames || !frames.length) { return; }
        var nodes = frames[this.frame % frames.length];
        var rows = this.mount && this.mount.orientations[this.orientation];
        if (rows) {
            this.drawMounted(nodes, rows);
        } else {
            this.drawCharacter(nodes, null, this.scale, 1);
        }
        ctx.setTransform(1, 0, 0, 1, 0, 0);
    };

    // Drawn in place of the slot, which puts the near leg in front.
    CharacterPreview.prototype.drawMounted = function (nodes, rows) {
        var size = (this.look.mount.scale || 100) / 100;
        var scale = this.baseScale * size;
        var seated = false;
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            if (row.rider !== undefined) {
                if (row.rider === this.look.mount.slot && !seated) {
                    seated = true;
                    // The seat scales with the mount, the rider does not.
                    this.drawCharacter(nodes, row.m, scale, (this.look.scale || 1) / size);
                }
                continue;
            }
            this.paint(row.m, this.mount.parts[row.part], this.mountImage(row.part),
                       row.slot ? this.mountColors[row.slot] : null, scale);
        }
        if (!seated) { this.drawCharacter(nodes, null, this.scale, 1); }
    };

    CharacterPreview.prototype.drawCharacter = function (nodes, seat, scale, breed) {
        for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i];
            var list = node.node.indexOf('Tete') === 0
                ? this.headEntries() : this.entriesFor(node.node);
            var m = seat ? compose(seat, scaledBy(breed, node.m)) : node.m;
            for (var j = 0; j < list.length; j++) {
                var entry = list[j];
                this.paint(m, this.manifests[entry.skin][entry.part],
                           this.image(entry.skin),
                           entry.slot ? this.colors[entry.slot] : null, scale);
            }
        }
    };

    CharacterPreview.prototype.paint = function (m, bounds, img, rgb, scale) {
        if (!bounds || !img.complete || !img.naturalWidth) { return; }
        var rx = m[0], ux = m[1], tx = m[2];
        var ry = m[3], uy = m[4], ty = m[5];
        var ppu = bounds.ppu;
        var ox = bounds.x - PAD / ppu;
        var oy = bounds.y + PAD / ppu;
        var s = scale;
        this.ctx.setTransform(
            s * rx / ppu, -s * ry / ppu, -s * ux / ppu, s * uy / ppu,
            s * (rx * ox + ux * oy + tx) + this.origin[0],
            -s * (ry * ox + uy * oy + ty) + this.origin[1]);
        // Skins come from one sheet and carry their spot on it; a mount piece
        // is still its own file and has none.
        var sx = bounds.sx || 0, sy = bounds.sy || 0;
        if (rgb) {
            this.ctx.drawImage(this.tinted(img, rgb, sx, sy, bounds.w, bounds.h), 0, 0);
        } else if (bounds.sx === undefined) {
            this.ctx.drawImage(img, 0, 0);
        } else {
            this.ctx.drawImage(img, sx, sy, bounds.w, bounds.h,
                               0, 0, bounds.w, bounds.h);
        }
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
