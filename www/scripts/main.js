angular.module('stackInABoxApp', []).controller('StackInABoxCtrl',
    ['$scope', function($scope) {
    $scope.extVSwitches = [];
    $scope.extVSwitch = null;
    $scope.newExtVSwitch = null;
    $scope.hostNics = [];
    $scope.hostNic = null;
    $scope.adminPassword = null;
    $scope.centosMirror = null;
    $scope.centosMirrors = null;
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
    $scope.computeNodes = null;
}]);

function handleError(msg) {
    showMessage('Error', msg);

}

function showMessage(caption, msg) {
    $("#showError").addClass("active-page");
    $("#errormessageok").focus();
    $("#errorcaption").text(caption);
    $("#errormessage").text(msg);
    $(".nano").nanoScroller();
}

function showPage(pageSelector) {
    $(".active-page").removeClass("active-page");
    $(pageSelector).addClass("active-page");
    $(pageSelector).focus();
}

function hidePage(pageSelector) {
    $(pageSelector).removeClass("active-page");
}

function showWelcome() {
    showPage("#intro");
    $(".progress_bar").css('display','none');
    $(".progress_bar_text").css('display','none');
}

function showEula() {
    showPage("#page-1");
    $(".nano").nanoScroller();
    $(".progress_bar").css('display','none');
    $(".progress_bar_text").css('display','none');
}

function showDeploymentDetails(controllerIp, horizonUrl) {

    // TODO: move data retrieveal to a separate event
    var $scope = angular.element("#maindiv").scope();
    $scope.controllerIp = controllerIp;
    $scope.horizonUrl = horizonUrl;
    $scope.$apply();

    showPage("#control-panel");
}

function updateComputeNodesView(computeNodes) {
    var $scope = angular.element("#maindiv").scope();
    $scope.computeNodes = JSON.parse(computeNodes);
    $scope.$apply();
}

function showControllerConfig() {
    showPage("#page-2");
    $(".progress_bar").css('display','inline-block');
    $(".progress_bar_text").css('display','inline-block');
}

function showHostConfig() {
    showPage("#host-setup");
}

function reviewConfig() {
    showPage("#review");
}

function installDone(success) {
}

function enableRetryDeployment(enable) {
    if(enable) {
        $("#reconfig-install").css('display','inline-block');
        $("#retry-install").css('display','inline-block');
        $("#cancel-install").css('display','none');
    } else {
        $("#reconfig-install").css('display','none');
        $("#retry-install").css('display','none');
        $("#cancel-install").css('display','block');
    }
}

function installStarted() {
    //$("#getopenstackbutton").attr("disable", "disable");
    showPage("#install-page");
    //setupTerm();
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

function getDeploymentConfigDict() {
    var $scope = angular.element("#maindiv").scope();

    var dict = {};
    dict["ext_vswitch_name"] = $scope.extVSwitch;
    dict["centos_mirror"] = $scope.centosMirror;
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
    return dict
}

function startInstall() {
    console.log("startInstall!");
    try {
        term.reset();
        controller.install(JSON.stringify(getDeploymentConfigDict()));
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
        $("#createswitchdialogokwrap").css('color','#A0A0A0');
        $("#createswitchdialogokicon").css('color','#A0A0A0');
        $("#createswitchdialogcancelwrap").css('color','#A0A0A0');
        $("#createswitchdialogcancelicon").css('color','#A0A0A0');
        $("#spinner").css('display','inline-block');
        $("#blocker").css('display','inherit');
    } else {
        $("#createswitchdialogok").removeAttr('disabled');
        $("#createswitchdialogcancel").removeAttr('disabled');
        $("#createswitchdialogokwrap").css('color','#FFFFFF');
        $("#createswitchdialogokicon").css('color','#0099CC');
        $("#createswitchdialogcancelwrap").css('color','#FFFFFF');
        $("#createswitchdialogcancelicon").css('color','#0099CC');
        $("#spinner").css('display','none');
        $("#blocker").css('display','none');
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

function addExtVSwitchCompleted(vswitch_name) {
    enableAddExtVSwitchDialogControls(true);
    hidePage("#createswitch");

    var $scope = angular.element("#maindiv").scope();
    $scope.extVSwitch = vswitch_name
    $scope.$apply();

    $("#extvswitch").selectmenu("refresh", true);
}

function productUpdateAvailable(currentVersion, newVersion, updateRequired, updateUrl) {
    updateMessage = 'An updated version of this product is available at "' +
                    updateUrl + '" ';
    updateMessage += 'It is recommended to close this application and ' +
                     'download the updated version before continuing. ';
    updateMessage += 'Current version: ' + currentVersion + '. ';
    updateMessage += 'New available version: ' + newVersion;

    showMessage('v-magine update available', updateMessage);
}

function showProgressStatus(enable, step, total_steps, msg) {
    if(enable) {
        $('#progress_bar_id').css('display', 'inline-block');
        $("#spinner").css('display','inline-block');
        $('#progress_bar_msg').text(msg);
    }
    else {
        $('#progress_bar_id').css('display','none');
        $("#spinner").css('display','none');
        $('#progress_bar_msg').text(msg);
    }
}

function tooltips() {
    $(".has_tooltip").hover(function(){
        if(!$('#progress_bar_msg').text()) {
            $('#progress_bar_msg').text($(this).attr('data-tooltip'));
        }
    }, function(){
        if(($('#progress_bar_msg').text()) == ($(this).attr('data-tooltip'))) {
            $('#progress_bar_msg').text('');
        }
    });
}

function disableDeployment() {
    $("#controllerconfignext").attr('disabled','disabled');
}

function configCompleted(configJson) {
    if(!configJson)
        return;

    var defaultConfig = JSON.parse(configJson);

    var $scope = angular.element("#maindiv").scope();
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

    initControllerMemSlider();
}

function getRepoUrlsCompleted(repoUrlJson) {
    var repoUrlDict = JSON.parse(repoUrlJson);

    var $scope = angular.element("#maindiv").scope();
    $scope.centosMirror = repoUrlDict.repo_url;
    $scope.centosMirrors = repoUrlDict.repo_urls;
    $scope.$apply();

    $("#centosmirror").selectmenu("refresh", true);
}

function setDefaultConfigValues() {
    controller.get_config();
}

function showPassword(x){
    x.type = "text";
}

function hidePassword(x){
    x.type = "password";
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

function initRepoUrlSelect() {
    $("#centosmirror").selectmenu({
        change: function(event, ui) {
            // AngularJs two way databinding does not work
            // with selectmenu
            var value = $(this).val();
            var $scope = angular.element(this).scope();
            $scope.$apply(function() {
                $scope.centosMirror = $scope.centosMirrors[value];
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

    $("#confirmmessageno").click(function(){
        hidePage("#showConfirm");
        return false;
    });

    $("#showError").keypress(function(event) {
        if ((event.which == 13) && ($("#showError").hasClass("active-page"))) {
            hidePage("#showError");
        }
        return false;
    });

    $("#controllerconfignext").click(function(){
        if((validateControllerConfigForm()) && (validateIP())) {
            controller.show_host_config();
        }
        $("#adminpassword").removeClass("hide_validation");
        $("#adminpasswordrepeat").removeClass("hide_validation");
        return false;
    });

    $("#hostconfigback").click(function(){
        controller.show_controller_config();
        return false;
    });

    $("#hostconfignext").click(function(){
        if(validateHostConfigForm()) {
            controller.review_config(
                JSON.stringify(getDeploymentConfigDict()));
        }
        $("#hypervhostusername").removeClass("hide_validation");
        $("#hypervhostpassword").removeClass("hide_validation");
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

    $("#add-edit, #migrate").click(function(){
        showMessage("Coming soon!", "This feature will be available in a forthcoming update!");
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

    $("#retry-install").click(function(){
        startInstall();
        return false;
    });

    $("#cancel-install").click(function(){
        controller.cancel_deployment();
        return false;
    });

    $("#reconfig-install").click(function(){
        controller.reconfig_deployment();
        return false;
    });

    $("#agreement").load("eula.html");

    $('#showhorizonbutton').click(function(){
        controller.open_horizon_url();
        return false;
    });

    $('#opencontrollersshbutton, #controllerip').click(function(){
        controller.open_controller_ssh();
        return false;
    });

    $('#redeployopenstack').click(function(){
        controller.redeploy_openstack();
        return false;
    });

    $('#removeopenstack').click(function(){
        controller.remove_openstack();
        return false;
    });

    setPasswordValidation();
    initControllerMemSlider();

    $("#selectdistro").selectmenu();
    $("#pxe-interface").selectmenu();
    $("#bmc-type").selectmenu();
    $("#bmc-type2").selectmenu();
    initRepoUrlSelect();
    initExtVSwitchSelect();
    initHostNicsSelect();

    setupTerm();
}

function validations() {
    $("#adminpassword").change(function(){
        $("#adminpassword").removeClass("hide_validation");
        $("#adminpasswordrepeat").removeClass("hide_validation");
        return false;
    });

    $("#fiprangestart").focus(function(){
        $("#fiprangestart").removeClass("is_invalid");
        return false;
    });

    $("#fiprangeend").focus(function(){
        $("#fiprangeend").removeClass("is_invalid");
        return false;
    });

    $("#subnet").focus(function(){
        $("#subnet").removeClass("is_invalid");
        return false;
    });

    $("#gateway").focus(function(){
        $("#gateway").removeClass("is_invalid");
        return false;
    });

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

function validateIP() {
    var subnet_format = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/([0-3]?[0-9]?)$/;
    var ip_format = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    var subnet = $("#subnet").val();
    var ip_start = $("#fiprangestart").val();
    var ip_end = $("#fiprangeend").val();
    var gateway = $("#gateway").val();
    var prefix = subnet.split('/').slice(1);
    var prefix_length = 0;

    if ((prefix >= 8) && (prefix <=15)) {
        prefix_length = 1;
    } else if ((prefix >= 16) && (prefix <=23)) {
        prefix_length = 2;
    } else if ((prefix >= 24) && (prefix <=32)) {
        prefix_length = 3;
    } else {
        showMessage("OpenStack configuration",
                    "Please enter a valid prefix length");
        $("#subnet").focus();
        $("#subnet").addClass("is_invalid");
        return false;
    }

    var part = subnet.split('.').slice(0,prefix_length);
    var range = part.join('.');

    if(!subnet.match(subnet_format)) {
        showMessage("OpenStack configuration",
                    "Please enter a valid floating IP subnet");
        $("#subnet").focus();
        $("#subnet").addClass("is_invalid");
        return false;
    }

    part = ip_start.split('.').slice(0,prefix_length);
    var iprange = part.join('.');
    if(!(ip_start.match(ip_format)) || (range != iprange)) {
        showMessage("OpenStack configuration",
                    "Please enter a valid IP");
        $("#fiprangestart").focus();
        $("#fiprangestart").addClass("is_invalid");
        return false;
    }

    part = ip_end.split('.').slice(0,prefix_length);
    iprange = part.join('.');
    if(!(ip_end.match(ip_format)) || (range != iprange)) {
        showMessage("OpenStack configuration",
                    "Please enter a valid IP");
        $("#fiprangeend").focus();
        $("#fiprangeend").addClass("is_invalid");
        return false;
    }

    part = gateway.split('.').slice(0,prefix_length);
    iprange = part.join('.');
    if(!(gateway.match(ip_format)) || (range != iprange)) {
        showMessage("OpenStack configuration",
                    "Please enter a valid gateway");
        $("#gateway").focus();
        $("#gateway").addClass("is_invalid");
        return false;
    }

    var part2 = ip_start.split('.').slice(prefix_length,prefix_length+1);
    var ip_start_compare = part2.join('.');

    part2 = ip_end.split('.').slice(prefix_length,prefix_length+1);
    var ip_end_compare = part2.join('.');

    if (ip_start_compare > ip_end_compare) {
        showMessage("OpenStack configuration",
                    "Floating IP range end is smaller than range start ");
        $("#fiprangeend").focus();
        $("#fiprangeend").addClass("is_invalid");
        return false;
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

        initUi();

        tooltips();

        validations();

        controller.on_show_welcome_event.connect(showWelcome);
        controller.on_show_eula_event.connect(showEula);
        controller.on_show_controller_config_event.connect(
            showControllerConfig);
        controller.on_show_host_config_event.connect(showHostConfig);
        controller.on_show_deployment_details_event.connect(
            showDeploymentDetails);
        controller.on_get_compute_nodes_completed_event.connect(
            updateComputeNodesView);
        controller.on_review_config_event.connect(reviewConfig);
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
        controller.on_show_progress_status_event.connect(
            showProgressStatus);
        controller.on_enable_retry_deployment_event.connect(
            enableRetryDeployment);
        controller.on_get_config_completed_event.connect(
            configCompleted);
        controller.on_deployment_disabled_event.connect(
            disableDeployment);
        controller.on_product_update_available_event.connect(
            productUpdateAvailable);
        controller.on_get_repo_urls_completed_event.connect(
            getRepoUrlsCompleted);

        setDefaultConfigValues();
     }
    catch(ex)
    {
        handleError(ex);
    }
}
