var initialStateStateEngine = null;
var changesPendingStateEngine = false;
function setChangesPendingStateEngine(v) {
    changesPendingStateEngine = v;
    $("#button-save").val(changesPendingStateEngine ? gettext("Save") : gettext("Saved"));
    $("#button-save-and-tailor").prop("disabled", !changesPendingStateEngine);
    $("#button-save").prop("disabled", !changesPendingStateEngine);
    $("#button-discard-changes").prop("disabled", !changesPendingStateEngine);
}

function defaultSendDataFunctionStateEngine() {
    return $('#main_form').serialize();
}

function tailorStateEngine() {
    loadingAndRunUnchecked();
    window.location = $("a.rerun-button").attr("href");
}

function saveStateEngine(postUrl, sendDataFunction, onDataReceivedFunction) {
    sendDataFunction = sendDataFunction || defaultSendDataFunctionStateEngine;
    dataToSend = sendDataFunction();
    if (dataToSend) {
        $.post(postUrl,
               dataToSend,
               function (data) {
                   setChangesPendingStateEngine(false);
                   initialStateStateEngine = data;
                   if (onDataReceivedFunction) {
                       onDataReceivedFunction(initialStateStateEngine);
                   }
               });
    }
}

function registerChangeableStateEngine(widget) {
    widget.on('change keypress paste textInput input', function() {
        setChangesPendingStateEngine(true);
    });
}

function registerClickableStateEngine(widget) {
    widget.click(function() {
        setChangesPendingStateEngine(true);
    });
}

function setupStateEngine(initFunction, postUrl, initialState, sendDataFunction, onDataReceivedFunction) {
    initialStateStateEngine = initialState;
    initFunction(initialStateStateEngine);
    setChangesPendingStateEngine(false);
    
    registerChangeableStateEngine($(".change-modifies-state"));
    registerClickableStateEngine($(".click-modifies-state"));

    $("#button-discard-changes").click(function(){
        initFunction(initialStateStateEngine);
        setChangesPendingStateEngine(false);
    });
    
    $("#button-save").click(function(){
        saveStateEngine(postUrl, sendDataFunction, onDataReceivedFunction);
    });
    
    $("#button-save-and-tailor").click(function(){
        saveStateEngine(postUrl, sendDataFunction, tailorStateEngine);
    });
}

$(window).on('beforeunload', function(){
    if (changesPendingStateEngine) {
        return gettext("You have unsaved changes. They will be discarded if you leave.");
    }
});

