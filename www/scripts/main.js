angular.module('stackInABoxApp', []).controller('StackInABoxCtrl',
    ['$scope', function($scope) {
    $scope.extVSwitches = [];
    $scope.extVSwitch = null;
    $scope.hostNics = [];
    $scope.hostNic = null;
    $scope.adminPassword = null;
    $scope.centosMirror = null;
    $scope.maxOpenStackVMMem = 0;
    $scope.minOpenStackVMMem = 0;
    $scope.openStackVMMem = 0;
    $scope.fipRange = null;
    $scope.fipRangeStart = null;
    $scope.fipRangeEnd = null;
    $scope.fipRangeGateway = null;
    $scope.fipRangeNameServers = [];
    $scope.openstackBaseDir = null;
    $scope.hypervHostUsername = null;
    $scope.hypervHostPassword = null;
}]);

function handleError(msg) {
    $('<div />').html(msg).dialog({
        modal: true,
        title: "Error",
        buttons: {
            Ok: function() {
                $(this).dialog("close");
            }
        }
    });
}

function showPage(pageSelector) {
    $(".active-page").removeClass("active-page");
    $(pageSelector).addClass("active-page");
}

function showWelcome() {
    showPage("#intro");
}

function showEula() {
    //showPage("#page-1");
}

function showDeploymentDetails() {
}

function showControllerConfig() {
    showPage("#page-2");
}

function reviewConfig() {
}

function installDone(success) {
    $('#getopenstackbutton').button("enable");
    $("#mainprogressbar").progressbar({ value: 0 });

    if(success) {
        $('#status').text('Your OpenStack is ready!');
    } else {
        $('#status').text('Ops, something went wrong. :-(');
    }
}

function installStarted() {
    $("#getopenstackbutton").button("disable");
    $("#maintabs").tabs({active: 2});
}

function statusChanged(msg, step, maxSteps) {
    $('#status').text(msg);
    $("#mainprogressbar").progressbar({ value: step,
                                        max: maxSteps });
}

function getExtVSwitchesCompleted(extVSwitchesJson) {
    var $scope = angular.element("#maintabs").scope();

    $scope.extVSwitches = JSON.parse(extVSwitchesJson);
    if(!$scope.extVSwitch && $scope.extVSwitches.length > 0) {
        $scope.extVSwitch = $scope.extVSwitches[0];
    }
    $scope.$apply();

    $("#extvswitch").selectmenu("refresh", true);
}

function getAvailableHostNicsCompleted(hostNicsJson) {
    var $scope = angular.element("#addextvswitchdialog").scope();

    $scope.hostNics = JSON.parse(hostNicsJson);
    $scope.hostNic = null;
    $scope.$apply();

    $("#hostnics").selectmenu("refresh", true);
}

function gotStdOutData(data){
    //console.log(data);
    term.write(data.replace('\n', '\r\n'));
}

function gotStdErrData(data){
    //console.log("err: " + data);
    term.write(data.replace('\n', '\r\n'));
}

function startInstall() {
    console.log("startInstall!");
    try {
        term.reset();

        var $scope = angular.element("#maintabs").scope();

        var dict = {};
        dict["ext_vswitch_name"] = $scope.extVSwitch;
        dict["openstack_vm_mem_mb"] = $scope.openStackVMMem;
        dict["openstack_base_dir"] = $scope.openstackBaseDir;
        dict["admin_password"] = $scope.adminPassword;
        dict["hyperv_host_username"] = $scope.hypervHostUsername;
        dict["hyperv_host_password"] = $scope.hypervHostPassword;
        dict["fip_range"] = $scope.fipRange;
        dict["fip_range_start"] = $scope.fipRangeStart;
        dict["fip_range_end"] = $scope.fipRangeEnd;
        dict["fip_gateway"] = $scope.fipRangeGateway;
        dict["fip_name_servers"] = $scope.fipRangeNameServers;

        controller.install(JSON.stringify(dict));
    }
    catch(ex)
    {
        handleError(ex);
    }
}

var term;

function setupTerm() {
    term_cols = 136
    term_rows = 36

    term = new Terminal({
        cols: term_cols,
        rows: term_rows,
        useStyle: true,
        screenKeys: true,
        cursorBlink: false
    });

    term.on('data', function(data) {
        // TODO: write back
    });

    controller.set_term_info('vt100', term_cols, term_rows)
    term.open($('#term')[0]);
}

function enableAddExtVSwitchDialogControls(enable) {
    var action = enable ? "enable" : "disable";
    $("#addextvswitchdialogok").button(action);
    $("#addextvswitchdialogcancel").button(action);
    $(".ui-dialog-titlebar-close").button(action);
}

function addExtVSwitch() {
    try {
        var $scope = angular.element("#addextvswitchdialog").scope();
        if($("#addextvswitchdialogform")[0].checkValidity()) {
            enableAddExtVSwitchDialogControls(false);
            controller.add_ext_vswitch($scope.extVSwitch,
                                       $scope.hostNic.name);
        }
    }
    catch(ex)
    {
        handleError(ex);
    }
}

function addExtVSwitchCompleted(success) {
    $("#addextvswitchdialog").dialog("close");
    enableAddExtVSwitchDialogControls(true);
}

function initAddExtVSwitchDialog() {
    dialog = $("#addextvswitchdialog").dialog({
        autoOpen: false,
        height: 300,
        width: 800,
        modal: true,

        buttons: [
        {
            id: "addextvswitchdialogok",
            text: "Ok",
            click: function() {
                addExtVSwitch();
                return false;
                }
        },
        {
            id: "addextvswitchdialogcancel",
            text: "Cancel",
            click: function() {
                dialog.dialog("close");
                }
        }],
        close: function() {
            dialog.find("form")[0].reset();
        }
    });

    $("#hostnics").selectmenu({
        change: function(event, ui) {
            // AngularJs two way databinding does not work
            // with selectmenu
            var value = $(this).val();
            var $scope = angular.element(this).scope();
            $scope.$apply(function() {
                $scope.hostNic = $scope.hostNics[value];
            });
        }
    });
}

function setDefaultConfigValues() {
    var configJson = controller.get_config();
    if(!configJson)
        return;

    var defaultConfig = JSON.parse(configJson);

    var $scope = angular.element("#maindiv").scope();
    $scope.centosMirror = defaultConfig.default_centos_mirror;
    $scope.maxOpenStackVMMem = defaultConfig.max_openstack_vm_mem_mb;
    $scope.minOpenStackVMMem = defaultConfig.min_openstack_vm_mem_mb;
    $scope.openStackVMMem = defaultConfig.suggested_openstack_vm_mem_mb;
    $scope.openstackBaseDir = defaultConfig.default_openstack_base_dir;
    $scope.hypervHostUsername = defaultConfig.default_hyperv_host_username;
    $scope.fipRange = defaultConfig.default_fip_range;
    $scope.fipRangeStart = defaultConfig.default_fip_range_start;
    $scope.fipRangeEnd = defaultConfig.default_fip_range_end;
    $scope.fipRangeGateway = defaultConfig.default_fip_range_gateway;
    $scope.fipRangeNameServers = defaultConfig.default_fip_range_name_servers;

    $scope.$apply();
}

function setPasswordValidation() {
    var p1 = $("#adminpassword")[0];
    var p2 = $("#adminpasswordrepeat")[0];
    $("#adminpassword, #adminpasswordrepeat").on("input", function() {
        if (p1.value != p2.value || p1.value == '' || p2.value == '') {
            p2.setCustomValidity('The password does not match');
        } else {
            p2.setCustomValidity('');
        }
    });
}

function initUi() {

    $("#deploy").click(function(){
        controller.show_eula();
    });

    $("#exit").click(function(){
        controller.refuse_eula();
    });

    $("#agree").click(function(){
        controller.accept_eula();
    });

    $("#controllerconfigeula").click(function(){
        controller.show_eula();
    });

    $("#controllerconfignext").click(function(){
        if(validateControllerConfigForm()) {
            //controller.review_config();
        }
        return false;
    });

    $("#agreement").load("eula.html");

    setPasswordValidation();

    $('#slider-step').noUiSlider({
        start: [ 2048 ],
        step: 512,
        range: {
            'min': [  512 ],
            'max': [ 8144 ]
        },
        format: wNumb({
            decimals: 0,
        })
    });

    $('#slider-step').Link('lower').to($('#slider-step-value'));

    /*
    setDefaultConfigValues();
    setupTerm();
    controller.get_ext_vswitches();

    setPasswordValidation();

    $("#extvswitch").selectmenu();
    $("#addextvswitch").button().click(function(){
        $("#addextvswitchdialog").dialog("open");
        controller.get_available_host_nics();
        return false;
    });

    var $scope = angular.element("#maintabs").scope();
    $("#openstackvmmemslider").slider({
        range: "min",
        value: $scope.openStackVMMem,
        min: $scope.minOpenStackVMMem,
        max: $scope.maxOpenStackVMMem,
        slide: function(event, ui) {
            var value = ui.value.toString();
            $("#openstackvmmem").val(value + "MB");
            // AngularJs is not performing two way databinding
            $scope.openStackVMMem = value
        }
    });

    $("#openstackvmmem").val(
        $("#openstackvmmemslider").slider("value").toString() + "MB");

    $("#maintabs").tabs({ beforeActivate: function(event, ui){
        var oldTabIndex = ui.oldTab.index();
        if(oldTabIndex == 0) {
            return validateConfigForm();
        }
    }});

    $("#reviewbutton").button().click(function(){
        if(validateConfigForm()) {
            controller.review_config();
        }
        return false;
    });

    $("#configbutton").button().click(function(){
        controller.show_config()
        return false;
    });

    initAddExtVSwitchDialog();

    $("#mainprogressbar").progressbar({ value: 0 });
    $("#getopenstackbutton").button().click(function(){
        startInstall();
    });
*/
}

function validateControllerConfigForm() {
    if(!$("#controllerconfigform")[0].checkValidity()) {
        showMessage("OpenStack configuration",
                    "Please provide all the required configuration values");
        return false;
    } else {
        var $scope = angular.element("#controllerconfigform").scope();
        $scope.$apply();
    }
    return true;
}

function showMessage(title, msg) {
    $('<div />').html(msg).dialog({
        modal: true,
        title: title,
        buttons: {
            Ok: function() {
                $(this).dialog("close");
            }
        }
    });
}

function ApplicationIsReady() {
    try {
        console.log("ApplicationIsReady!");

        initUi();

        setDefaultConfigValues();

        controller.on_show_welcome_event.connect(showWelcome);
        controller.on_show_eula_event.connect(showEula);
        controller.on_show_controller_config_event.connect(
            showControllerConfig);
        controller.on_show_deployment_details_event.connect(
            showDeploymentDetails);
        controller.on_review_config_event.connect(reviewConfig);
        controller.on_status_changed_event.connect(statusChanged);
        controller.on_stdout_data_event.connect(gotStdOutData);
        controller.on_stderr_data_event.connect(gotStdErrData);
        controller.on_error_event.connect(handleError);
        controller.on_install_done_event.connect(installDone);
        controller.on_install_started_event.connect(installStarted);
        controller.on_get_ext_vswitches_completed_event.connect(
            getExtVSwitchesCompleted);
        controller.on_get_available_host_nics_completed_event.connect(
            getAvailableHostNicsCompleted);
        controller.on_add_ext_vswitch_completed_event.connect(
            addExtVSwitchCompleted);
     }
    catch(ex)
    {
        handleError(ex);
    }
}
