# -*- coding: utf-8 -*-
"""A pet stored under its pre-mount number still shows on the build.

Ankama reclassified a number of pets as mounts. The catalogue gives mounts an
id space of their own -- `MOUNT_ID_OFFSET + ankama_id` instead of the bare
ankama_id (`itemscraper/get_equipments3.py`) -- so every build saved before the
reclassification kept a number that designates nothing today, and its pet
silently disappeared: the slot renders as the bare word "Pet".

Measured on the production copy before the fix: 26 341 builds had lost their
pet this way, 263 of them in the public gallery. Verified on two live shared
builds, where every other slot rendered its item and only the pet was blank.

`get_item_in_slot` recovers them, and refuses the recovery when what it finds
is not of the type the slot takes -- which is the half that matters. A fallback
that accepted anything would restore 26 341 pets and quietly invent gear
everywhere else.
"""
import pickle

from django.test import TestCase

from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.solution import get_solution
from fashionistapulp.modelresult import MOUNT_ID_OFFSET
from fashionistapulp.structure import get_structure


def a_pet_that_moved(structure):
    """A pet living in the mount id space whose old number is now free.

    Derived from the catalogue rather than hard-coded, so the test keeps
    meaning something after the catalogue is regenerated.
    """
    for item in structure.get_unique_items_by_type_and_level('Pet', 200):
        if item.id > MOUNT_ID_OFFSET \
                and structure.get_item_by_id(item.id - MOUNT_ID_OFFSET) is None:
            return item
    return None


class AStoredPetSurvivesTheMountRenumbering(TestCase):

    def setUp(self):
        self.structure = get_structure('dofus3')
        self.client.post('/createproject/', {
            'project': 'p', 'charname': 'P', 'level': '200',
            'class': 'Iop', 'where_to_go': 'wizard'})
        self.char = Char.objects.order_by('-id').first()
        self.assertEqual(200, self.client.get('/solution/%d/' % self.char.id,
                                              follow=True).status_code)

    def store_in_slot(self, slot, value):
        self.char.refresh_from_db()
        minimal = read_char_blob(self.char.minimal_solution, None,
                                 'minimal_solution', self.char)
        self.assertIsNotNone(minimal)
        minimal.item_per_slot[slot] = value
        self.char.minimal_solution = pickle.dumps(minimal)
        self.char.save()
        self.char.refresh_from_db()
        result = get_solution(self.char)
        self.assertIsNotNone(result)
        worn = {i.slot: i for i in result.item_list if i.slot and i.item_added}
        return worn.get(slot)

    def test_the_old_number_still_finds_the_pet(self):
        pet = a_pet_that_moved(self.structure)
        self.assertIsNotNone(
            pet, 'no pet in the catalogue moved into the mount id space: '
                 'this test can no longer see what it was written for')
        restored = self.store_in_slot('pet', pet.id - MOUNT_ID_OFFSET)
        self.assertIsNotNone(
            restored,
            'the pet slot is empty for stored id %d, which is "%s" (%d) since '
            'the mount renumbering' % (pet.id - MOUNT_ID_OFFSET, pet.name, pet.id))
        self.assertEqual(pet.id, restored.id)

    def test_the_same_number_is_refused_by_a_slot_of_another_type(self):
        """The other half: the fallback must not dress a slot in a mount.

        Without this, the whole test file would pass on a fallback that
        recovers any number at all, and 641 551 slots would start showing
        gear their author never chose.
        """
        pet = a_pet_that_moved(self.structure)
        self.assertIsNotNone(pet)
        for slot in ('hat', 'boots', 'ring1', 'weapon'):
            self.assertIsNone(
                self.store_in_slot(slot, pet.id - MOUNT_ID_OFFSET),
                'the %s slot accepted "%s", which is a Pet' % (slot, pet.name))

    def test_a_number_that_leads_nowhere_stays_empty(self):
        self.assertIsNone(self.store_in_slot('pet', 999999999))

    def test_the_old_blob_format_does_not_crash(self):
        """Builds saved long ago hold a ModelResultItem, not an id.

        4 960 of them are still in the database. `get_item_in_slot` must not
        try arithmetic on one.
        """
        from fashionistapulp.modelresult import ModelResultItem
        self.assertIsNone(self.store_in_slot('pet', ModelResultItem(None)))

    def test_an_ordinary_id_is_untouched(self):
        self.char.refresh_from_db()
        worn = {i.slot: i for i
                in get_solution(self.char).item_list if i.slot and i.item_added}
        self.assertGreaterEqual(len(worn), 12)
        for slot, item in worn.items():
            self.assertEqual(item.id, self.store_in_slot(slot, item.id).id)
