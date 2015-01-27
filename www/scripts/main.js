angular.module('stackInABoxApp', []).controller('StackInABoxCtrl',
    ['$scope', function($scope) {
    $scope.extVSwitches = [];
    $scope.extVSwitch = null;
    $scope.newExtVSwitch = null;
    $scope.hostNics = [];
    $scope.hostNic = null;
    $scope.adminPassword = null;
    $scope.centosMirror = null;
    $scope.maxOpenStackVMMem = 0;
    $scope.minOpenStackVMMem = 0;
    $scope.suggestedOpenStackVMMem = 0;
    $scope.openStackVMMem = 0;
    $scope.fipRange = null;
    $scope.fipRangeStart = null;
    $scope.fipRangeEnd = null;
    $scope.fipRangeGateway = null;
    $scope.fipRangeNameServers = [];
    $scope.openstackBaseDir = null;
    $scope.hypervHostUsername = null;
    $scope.hypervHostPassword = null;
    $scope.hypervHostName = null;
    $scope.controllerIp = null;
    $scope.horizonUrl = null;
}]);

function handleError(msg) {
    showMessage('Error', msg);
}

function showMessage(caption, msg) {
    $("#showError").addClass("active-page");
    $("#errorcaption").text(caption);
    $("#errormessage").text(msg);
}

function showPage(pageSelector) {
    $(".active-page").removeClass("active-page");
    $(pageSelector).addClass("active-page");
}

function hidePage(pageSelector) {
    $(pageSelector).removeClass("active-page");
}

function showWelcome() {
    showPage("#intro");
}

function showEula() {
    showPage("#page-1");
    $(".nano").nanoScroller();
}

function showDeploymentDetails(controllerIp, horizonUrl) {

    // TODO: move data retrieveal to a separate event
    var $scope = angular.element("#maindiv").scope();
    $scope.controllerIp = controllerIp;
    $scope.horizonUrl = horizonUrl;
    $scope.$apply();

    showPage("#control-panel");
}

function showControllerConfig() {
    showPage("#page-2");
}

function showHostConfig() {
    showPage("#host-setup");
}

function reviewConfig() {
    showPage("#review");
}

function installDone(success) {
    //$('#getopenstackbutton').button("enable");
    $("#mainprogressbar").progressbar({ value: 0 });

    if(success) {
        $('#status').text('Your OpenStack is ready!');
    } else {
        $('#status').text('Ops, something went wrong. :-(');
    }
}

function installStarted() {
    //$("#getopenstackbutton").attr("disable", "disable");
    showPage("#install-page");
    //setupTerm();
}

function statusChanged(msg, step, maxSteps) {
    $('#status').text(msg);
    $("#mainprogressbar").progressbar({ value: step,
                                        max: maxSteps });
}

function getExtVSwitchesCompleted(extVSwitchesJson) {
    var $scope = angular.element("#maindiv").scope();

    $scope.extVSwitches = JSON.parse(extVSwitchesJson);
    if(!$scope.extVSwitch && $scope.extVSwitches.length > 0) {
        $scope.extVSwitch = $scope.extVSwitches[0];
    }
    $scope.$apply();

    $("#extvswitch").selectmenu("refresh", true);
}

function getAvailableHostNicsCompleted(hostNicsJson) {
    var $scope = angular.element("#createswitch").scope();

    $scope.hostNics = JSON.parse(hostNicsJson);
    $scope.hostNic = null;
    $scope.$apply();

    $("#hostnics").selectmenu("refresh", true);
}

function gotStdOutData(data){
    console.log(data);
    term.write(data.replace('\n', '\r\n'));
}

function gotStdErrData(data){
    console.log("err: " + data);
    term.write(data.replace('\n', '\r\n'));
}

function startInstall() {
    console.log("startInstall!");
    try {
        term.reset();

        var $scope = angular.element("#maindiv").scope();

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
    term_rows = 25

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
    if(!enable) {
        $("#createswitchdialogok").attr('disabled','disabled');
        $("#createswitchdialogcancel").attr('disabled','disabled');
    } else {
        $("#createswitchdialogok").removeAttr('disabled');
        $("#createswitchdialogcancel").removeAttr('disabled');
    }
}

function addExtVSwitch() {
    try {
        var $scope = angular.element("#createswitchdialog").scope();
        if($("#addextvswitchdialogform")[0].checkValidity()) {
            enableAddExtVSwitchDialogControls(false);
            controller.add_ext_vswitch($scope.newExtVSwitch,
                                       $scope.hostNic.name);
        } else {
            showMessage("OpenStack configuration",
                        "Please provide all the required configuration values");
        }
    }
    catch(ex)
    {
        handleError(ex);
    }
}

function addExtVSwitchCompleted(success) {
    enableAddExtVSwitchDialogControls(true);
    hidePage("#createswitch");
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
    $scope.suggestedOpenStackVMMem = $scope.openStackVMMem
    $scope.openstackBaseDir = defaultConfig.default_openstack_base_dir;
    $scope.hypervHostUsername = defaultConfig.default_hyperv_host_username;
    $scope.fipRange = defaultConfig.default_fip_range;
    $scope.fipRangeStart = defaultConfig.default_fip_range_start;
    $scope.fipRangeEnd = defaultConfig.default_fip_range_end;
    $scope.fipRangeGateway = defaultConfig.default_fip_range_gateway;
    $scope.fipRangeNameServers = defaultConfig.default_fip_range_name_servers;
    $scope.hypervHostName = defaultConfig.localhost;

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

function initControllerMemSlider() {

    var $scope = angular.element("#maindiv").scope();
    $("#openstackvmmemslider").slider({
        range: "min",
        value: $scope.openStackVMMem,
        min: $scope.minOpenStackVMMem,
        max: $scope.maxOpenStackVMMem,
        slide: function(event, ui) {
            var value = ui.value.toString();
            $("#openstackvmmem").text(value + "MB");
            // AngularJs is not performing two way databinding
            $scope.openStackVMMem = value;

            var color = '#37A8DF';
            if (value < $scope.suggestedOpenStackVMMem) {
                color = '#BC1D2C';
            }
            $('.ui-slider-range-min').css('background-color', color);
        }
    });

    $("#openstackvmmem").val(
        $("#openstackvmmemslider").slider("value").toString() + "MB");
}

function initHostNicsSelect() {
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

function initExtVSwitchSelect() {
    $("#extvswitch").selectmenu({
        change: function(event, ui) {
            // AngularJs two way databinding does not work
            // with selectmenu
            var value = $(this).val();
            var $scope = angular.element(this).scope();
            $scope.$apply(function() {
                $scope.extVSwitch = $scope.extVSwitches[value];
            });
        }
    });
}

function initUi() {

    $("#deploy").click(function(){
        controller.show_eula();
        return false;
    });

    $("#exit").click(function(){
        controller.refuse_eula();
        return false;
    });

    $("#agree").click(function(){
        controller.accept_eula();
        return false;
    });

    $("#controllerconfigeula").click(function(){
        controller.show_eula();
        return false;
    });

    $("#errormessageok").click(function(){
        hidePage("#showError");
        return false;
    });

    $("#controllerconfignext").click(function(){
        if(validateControllerConfigForm()) {
            controller.show_host_config();
        }
        return false;
    });

    $("#hostconfigback").click(function(){
        controller.show_controller_config();
        return false;
    });

    $("#hostconfignext").click(function(){
        if(validateHostConfigForm()) {
            controller.review_config();
        }
        return false;
    });

    $("#createswitchdialogok").click(function(){
        addExtVSwitch();
        return false;
    });

    $("#createswitchdialogcancel").click(function(){
        // TODO add a controller action
        hidePage("#createswitch");
        return false;
    });

    $("#createSwitch").click(function(){
        // TODO add a controller action
        controller.get_available_host_nics();

        var $scope = angular.element("#createswitchdialog").scope();
        $scope.newExtVSwitch = null;
        $scope.hostNic = null;
        $scope.$apply();

        $("#createswitch").addClass("active-page");
        return false;
    });

    $("#configbutton").click(function(){
        controller.show_host_config()
        return false;
    });

    $("#getopenstackbutton").click(function(){
        startInstall();
        return false;
    });

    $("#cancel-install").click(function(){
        controller.cancel_deployment()
        return false;
    });

    $("#agreement").load("eula.html");

    $("#mainprogressbar").progressbar({ value: 0 });

    $('#showhorizonbutton').click(function(){
        controller.open_horizon_url();
        return false;
    });

    $('#opencontrollersshbutton').click(function(){
        controller.open_controller_ssh();
        return false;
    });

    $('#redeployopenstack').click(function(){
        controller.redeploy_openstack();
        return false;
    });

    setPasswordValidation();
    initControllerMemSlider();

    $("#selectdistro").selectmenu();
    initExtVSwitchSelect();
    initHostNicsSelect();

    setupTerm();
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

function validateHostConfigForm() {
    if(!$("#hostconfigform")[0].checkValidity()) {
        showMessage("OpenStack configuration",
                    "Please provide all the required configuration values");
        return false;
    } else {
        var $scope = angular.element("#hostconfigform").scope();
        $scope.$apply();
    }
    return true;
}

function ApplicationIsReady() {
    try {
        console.log("ApplicationIsReady!");

        setDefaultConfigValues();

        initUi();

        controller.on_show_welcome_event.connect(showWelcome);
        controller.on_show_eula_event.connect(showEula);
        controller.on_show_controller_config_event.connect(
            showControllerConfig);
        controller.on_show_host_config_event.connect(showHostConfig);
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
