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
    $scope.fipRangeStart = null;
    $scope.fipRangeEnd = null;
    $scope.openstackBaseDir = null;
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

function installDone(success) {
    $('#getopenstackbutton').button("enable");
    $('#status').text('');
    $("#mainprogressbar").progressbar({ value: 0 });
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
        controller.install($scope.extVSwitch, $scope.openstackBaseDir);
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

    var $scope = angular.element("#maintabs").scope();
    $scope.centosMirror = defaultConfig.default_centos_mirror;
    $scope.maxOpenStackVMMem = defaultConfig.max_openstack_vm_mem_mb;
    $scope.minOpenStackVMMem = defaultConfig.min_openstack_vm_mem_mb;
    $scope.openStackVMMem = defaultConfig.suggested_openstack_vm_mem_mb;
    $scope.openstackBaseDir = defaultConfig.default_openstack_base_dir;
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
            $("#openstackvmmem").val(ui.value.toString() + "MB");
        }
    });

    $("#openstackvmmem").val(
        $("#openstackvmmemslider").slider("value").toString() + "MB");

    $('#fiprangestart, #fiprangeend').ipAddress().on("blur", function(val) {
        var ui = $(this)[0];
        if(!ui.value.isIpv4()) {
            ui.setCustomValidity('Not a valid IP address');
        } else {
            // AngularJs is not performing two way databinding
            var $scope = angular.element(this).scope();
            $scope.$apply(function() {
                var model = ui.attributes['ng-model'].value;
                $scope[model] = ui.value;
            });
            ui.setCustomValidity('');
        }
    }).each(function() {
        $(this)[0].setCustomValidity('Please provide an IP address');
    });

    $("#maintabs").tabs({ beforeActivate: function(event, ui){
        var oldTabIndex = ui.oldTab.index();
        if(oldTabIndex == 0) {
            return validateConfigForm();
        }
    }});

    $("#reviewbutton").button().click(function(){
        if(validateConfigForm()) {
            $("#maintabs").tabs({active: 1});
        }
        return false;
    });

    $("#configbutton").button().click(function(){
        $("#maintabs").tabs({active: 0});
        return false;
    });

    initAddExtVSwitchDialog();

    $("#mainprogressbar").progressbar({ value: 0 });
    $("#getopenstackbutton").button().click(function(){
        $(this).button("disable");
        $("#maintabs").tabs({active: 2});
        startInstall();
    });
}

function validateConfigForm() {
    if(!$("#tabconfigform")[0].checkValidity()) {
        showMessage("OpenStack configuration",
                    "Please provide all the required configuration values");
        return false;
    } else {
        var $scope = angular.element("#maintabs").scope();
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

        controller.on_status_changed_event.connect(statusChanged);
        controller.on_stdout_data_event.connect(gotStdOutData);
        controller.on_stderr_data_event.connect(gotStdErrData);
        controller.on_error_event.connect(handleError);
        controller.on_install_done_event.connect(installDone);
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
