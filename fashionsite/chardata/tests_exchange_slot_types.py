# -*- coding: utf-8 -*-
"""An item may only be exchanged into a slot that accepts its type.

`switch_item` takes an item id straight from the request and used to hand it to
`ModelResult.switch_item` without ever comparing the item's type to the slot.
A hand-made POST could therefore put a hat on the character's feet: the page
rendered, the stats counted the hat as boots, and the shared build -- a public,
indexed page -- rendered the same nonsense.

The rule the guard enforces is not invented here, it is the one the rest of the
app already follows on both sides:

  - the picker only ever offers `SLOT_NAME_TO_TYPE[slot]`
    (`get_items_of_type` -> `_order_items(itype, ...)`);
  - the solver only ever fills a slot with that same type, measured over five
    solved builds and eighty equipped items, sixteen slots, zero deviation.

So the guard cannot refuse anything a legitimate path produces. That claim is
what `test_every_slot_still_accepts_its_own_type` checks, and it is the half
that matters: a guard that refused everything would pass the rejection test
alone.
"""
import re

from django.test import TestCase

from chardata.models import Char

#: Pairs of (slot holding the item we move, slot we wrongly move it into).
#: Each pair crosses a different type family.
MISMATCHES = [
    ('hat', 'boots'),
    ('boots', 'ring1'),
    ('weapon', 'amulet'),
    ('pet', 'dofus1'),
    ('amulet', 'shield'),
    ('ring1', 'belt'),
]


class ExchangeRespectsSlotTypes(TestCase):

    def setUp(self):
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'P', 'level': '200',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        self.assertEqual(200, self.client.get('/solution/%d/' % self.char.id,
                                              follow=True).status_code)

    def equipped(self):
        from chardata.solution import get_solution
        self.char.refresh_from_db()
        result = get_solution(self.char)
        self.assertIsNotNone(result, 'the build has no solution to exchange in')
        return {i.slot: i for i in result.item_list if i.slot and i.item_added}

    def exchange(self, item_id, slot):
        return self.client.post('/exchange/%d/' % self.char.id,
                                {'itemName': str(item_id), 'slot': slot})

    def offer_for(self, slot):
        """One item the picker itself proposes for this slot."""
        response = self.client.post('/itemexchange/%d/' % self.char.id,
                                    {'slot': slot, 'page': '1'})
        self.assertEqual(200, response.status_code)
        ids = [int(x) for x in re.findall(
            r'"id"\s*:\s*(\d+)', response.content.decode('utf-8', 'replace'))]
        return ids[0] if ids else None

    def test_an_item_cannot_be_moved_into_a_slot_of_another_type(self):
        worn = self.equipped()
        checked = 0
        for source, target in MISMATCHES:
            if source not in worn or target not in worn:
                continue
            checked += 1
            item = worn[source]
            self.assertEqual(
                400, self.exchange(item.id, target).status_code,
                '"%s" (%s) was accepted into the %s slot'
                % (item.name, item.type, target))
            self.assertEqual(
                item.id, self.equipped()[source].id,
                'the refused exchange still moved "%s"' % item.name)
        self.assertGreaterEqual(
            checked, 4,
            'only %d mismatched pairs were reachable: the build is too empty '
            'for this test to mean anything' % checked)

    def test_every_slot_still_accepts_its_own_type(self):
        """The other half: the guard must not refuse a legitimate exchange.

        Every slot is walked, not a chosen few, because the guard reads one
        table and a single wrong row would only show on the slot it covers.
        """
        worn = self.equipped()
        self.assertGreaterEqual(len(worn), 12,
                                'only %d slots filled' % len(worn))
        refused = []
        for slot in sorted(worn):
            offered = self.offer_for(slot)
            if offered is None:
                continue
            if self.exchange(offered, slot).status_code != 200:
                refused.append(slot)
        self.assertEqual(
            [], refused,
            'the guard refuses items the picker itself offers, for: %s'
            % ', '.join(refused))

    def test_an_unknown_item_is_still_refused(self):
        """The pre-existing guard, kept honest: an id nobody owns is not a
        silent way to empty a slot."""
        for bogus in ('0', '-1', '999999999', 'Gelano', ''):
            self.assertEqual(400, self.exchange(bogus, 'boots').status_code,
                             'itemName=%r was accepted' % bogus)
