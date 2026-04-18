var sliderTemplate =
'<div class="wizard-slider-container"> \
    <div class="wizard-slider-arrow-cell"></div> \
    <div class="wizard-slider-label">%label%</div> \
    <div class="wizard-slider-container-slider"> \
        <input type="hidden" name="slider_%id_suffix%"> \
        <div class="wizard-slider wizard-slider-main-slider" id="slider_%id_suffix%"></div> \
    </div> \
    <div class="wizard-slider-value"></div> \
</div>';

var arrowImageTemplate = null;

function template(t, data){
    return t.replace(/%(\w*)%/g,
        function(m, key){
            return data.hasOwnProperty(key) ? data[key] : "";
        });
}

function resolveAndAppend(section, t, data) {
    var resolved = $(template(t, data));
    section.append(resolved);
    return resolved;
}

function createSecondarySection(section, mainData) {
    var arrowImage = $(arrowImageTemplate)
    var mainSlider = resolveAndAppend(section, sliderTemplate, mainData);
    mainSlider.find(".wizard-slider-arrow-cell").append(arrowImage);
    var secondarySection = $('<div class="wizard-slider-section-secondary"></div>');
    section.append(secondarySection);
    
    arrowImage.click(function() {
        if (secondarySection.is(":visible")) {
            arrowImage.removeClass("rotated");
        } else {
            arrowImage.addClass("rotated");
        }
        secondarySection.slideToggle(250);
    });
    
    // Switch commented line to toggle sections starting open or closed.
    secondarySection.hide();
    // arrowImage.addClass("rotated");
    
    return {slider: mainSlider, section: secondarySection};
}

function wizardSliderSetupWidget(container, data) {
    var slider = container.find(".wizard-slider");
    var label = container.find(".wizard-slider-value");
    
    var updateValueLabel = function(event, ui) {
        var newValue = ui.value;
        label.html(newValue);
        slider.prev().val(newValue);
    }
    
    var initialValue = Math.round(data.abs_value);
    slider.slider(
        {min: data.min_value,
         max: data.max_value,
         value: initialValue,
         change: updateValueLabel,
         slide: updateValueLabel});
    updateValueLabel(null, {value: initialValue});
    
}

function wizardSlidersInit(initialDataSliders, arrowImageUrl) {
    arrowImageTemplate = '<img class="triangle-img" src="' + arrowImageUrl + '">';

    var sliderSection = $(".wizard-section-sliders");
    
    $.each(initialDataSliders, function(i, mainSlider) {
        if (mainSlider.subsliders != null) {
            if (mainSlider.subsliders.length > 0) {
                var sectionResult = createSecondarySection(sliderSection,
                    {id_suffix: mainSlider.key, label: mainSlider.name});
                sectionResult.slider.find(".wizard-slider").hide();
                $.each(mainSlider.subsliders, function(j, secondarySlider) {
                    var secondaryResolved = resolveAndAppend(sectionResult.section,
                        sliderTemplate,
                        {id_suffix: secondarySlider.key, label: secondarySlider.name})
                    secondaryResolved.find(".wizard-slider-label").addClass("wizard-slider-secondary-label");
                    wizardSliderSetupWidget(secondaryResolved, secondarySlider, arrowImageUrl);
                });
            }
        } else {
            var mainResolved = resolveAndAppend(sliderSection, sliderTemplate,
                {id_suffix: mainSlider.key, label: mainSlider.name});
            wizardSliderSetupWidget(mainResolved, mainSlider);
        }
    });
    
}

function wizardSlidersReset(data){
    $.each(data, function(i, mainSlider) {
        if (mainSlider.subsliders != null) {
            if (mainSlider.subsliders.length > 0) {
                $.each(mainSlider.subsliders, function(j, secondarySlider) {
                    slider = $('#slider_' + secondarySlider.key);
                    slider.slider("option", "min", secondarySlider.min_value);
                    slider.slider("option", "max", secondarySlider.max_value);
                    slider.slider("option", "value", Math.round(secondarySlider.abs_value));
                });
            }
        } else {
            slider = $('#slider_' + mainSlider.key);
            slider.slider("option", "min", mainSlider.min_value);
            slider.slider("option", "max", mainSlider.max_value);
            slider.slider("option", "value", Math.round(mainSlider.abs_value));
        }
    });
}



