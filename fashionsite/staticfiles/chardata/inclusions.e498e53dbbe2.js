
$.ajaxSetup({
  data: {csrfmiddlewaretoken: '{{ csrf_token }}' },
});   

function inclusionsUpdateLine(item_id, slot, allItemsPerType, slotToType) {
    var type = slotToType[slot];
    var itemName = allItemsPerType[type][item_id];
    $("#" + slot + "-name").text(itemName);
    $.post("/getitemdetails/",
           {item: item_id},
           function(data) {
               $("#item-level-" + slot).text(gettext("Lvl.") + " " + data.level);
               $("#item-picture-" + slot).attr("src", data.file);
               $("#button-remove-" + slot).show();
               $("#item-id-"+slot).val(item_id);
               $("#button-add-" + slot).hide();
               $("#td-" + slot).attr('align', 'left');
           });
}

function removeItem(slot, images){
    $("#item-level-" + slot).text("");
    $("#item-picture-" + slot).attr("src", images[slot]);
    $("#button-remove-" + slot).hide();
    $("#item-id-"+slot).val("");
    $("#item-id-"+slot).change();
    $("#button-add-" + slot).show();
    $("#" + slot + "-name").text("");
    $("#td-" + slot).attr('align', 'center');
}

function inclusionsInit(inclusionsData, allItemsPerType, allItemsPerTypeAndName, slotToType, slotImages) {
    $.each(inclusionsData, function(slot, equip) {
        $("#item-picture-" + slot).attr("src", slotImages[slot]);
        $("#button-remove-" + slot).hide();
        $("#button-add-" + slot).show();
        $("#td-" + slot).attr('align', 'center');
        $("#button-remove-" + slot).click(function(){
            removeItem(slot, slotImages);
        });
        if (equip != '') {
            inclusionsUpdateLine(equip, slot, allItemsPerType, slotToType);
        }
    });
}

