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
      $scope.maxOpenStackVMCpu = 0;
      $scope.minOpenStackVMCpu = 0;
      $scope.suggestedOpenStackVMCpu = 0;
      $scope.openStackVMCpu = 0;
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
      $scope.downloadUrl = null;
      $scope.computeNodes = null;
      $scope.useProxy = false;
      $scope.proxyUrl = null;
      $scope.proxyUsername = null;
      $scope.proxyPassword = null;
      $scope.mgmtExtDhcp = true;
      $scope.mgmtExtIp = null;
      $scope.mgmtExtNetmask = null;
      $scope.mgmtExtGateway = null;
      $scope.mgmtExtNameServers = [];
      $scope.useProxy = true;
  }]);

function handleError(msg) {
    showMessage('Error', msg);
}

function showMessage(caption, msg) {
    $("#showError").addClass("error-visible");
    $("#errormessageok").focus();
    $("#errorcaption").text(caption);
    $("#errormessage").text(msg);
    $(".nano").nanoScroller();
}

function showDownload(caption, msg) {
    $("#showDownload").addClass("error-visible");
    $("#downloadmessagelater").focus();
    $("#downloadcaption").text(caption);
    $("#downloadmessage").text(msg);
    $(".nano").nanoScroller();

}

function showPage(pageSelector) {
    $(".active-page").removeClass("active-page");
    $(pageSelector).addClass("active-page");
    $(pageSelector).focus();
}

function hidePage(pageSelector) {
    $(pageSelector).removeClass("active-page");
    $(pageSelector).removeClass("error-visible");
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

function controllerConfigValidated() {
    controller.show_openstack_networking_config();
    $("#adminpassword").removeClass("hide_validation");
    $("#adminpasswordrepeat").removeClass("hide_validation");
}

function openStackNetworkingConfigValidated() {
    controller.show_host_config();
}

function showOpenStackNetworkingConfig() {
    showPage("#page-openstack-networking");
}

function showHostConfig() {
    showPage("#host-setup");
}

function hostConfigValidated() {
    controller.show_review_config();
}

function showReviewConfig() {
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
    $scope.hostNic = '';
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
    dict["openstack_vm_vcpu_count"] = $scope.openStackVMCpu;
    dict["openstack_base_dir"] = $scope.openstackBaseDir;
    dict["admin_password"] = $scope.adminPassword;
    dict["hyperv_host_username"] = $scope.hypervHostUsername;
    dict["hyperv_host_password"] = $scope.hypervHostPassword;
    dict["fip_range"] = $scope.fipRange;
    dict["fip_range_start"] = $scope.fipRangeStart;
    dict["fip_range_end"] = $scope.fipRangeEnd;
    dict["fip_gateway"] = $scope.fipRangeGateway;
    dict["fip_name_servers"] = $scope.fipRangeNameServers;
    dict["use_proxy"] = $scope.useProxy;
    dict["proxy_url"] = $scope.proxyUrl;
    dict["proxy_username"] = $scope.proxyUsername;
    dict["proxy_password"] = $scope.proxyPassword;
    dict["mgmt_ext_dhcp"] = $scope.mgmtExtDhcp;
    dict["mgmt_ext_ip"] = $scope.mgmtExtIp;
    dict["mgmt_ext_netmask"] = $scope.mgmtExtNetmask;
    dict["mgmt_ext_gateway"] = $scope.mgmtExtGateway;
    dict["mgmt_ext_name_servers"] = $scope.mgmtExtNameServers;
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
    console.log("Setting selected external vswitch: " + vswitch_name);
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

    showDownload('v-magine update available', updateMessage);
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
    $scope.maxOpenStackVMCpu = defaultConfig.max_openstack_vm_vcpu_count;
    $scope.minOpenStackVMCpu = defaultConfig.min_openstack_vm_vcpu_count;
    $scope.openStackVMCpu = defaultConfig.suggested_openstack_vm_vcpu_count;
    $scope.suggestedOpenStackVMCpu = $scope.openStackVMCpu
    $scope.openstackBaseDir = defaultConfig.default_openstack_base_dir;
    $scope.hypervHostUsername = defaultConfig.default_hyperv_host_username;
    $scope.fipRange = defaultConfig.default_fip_range;
    $scope.fipRangeStart = defaultConfig.default_fip_range_start;
    $scope.fipRangeEnd = defaultConfig.default_fip_range_end;
    $scope.fipRangeGateway = defaultConfig.default_fip_range_gateway;
    $scope.fipRangeNameServers = defaultConfig.default_fip_range_name_servers;
    $scope.useProxy = defaultConfig.default_use_proxy;
    $scope.proxyUrl = defaultConfig.default_proxy_url;
    $scope.mgmtExtDhcp = defaultConfig.default_mgmt_ext_dhcp;
    $scope.mgmtExtNameServers = defaultConfig.default_mgmt_ext_name_servers;
    $scope.hypervHostName = defaultConfig.localhost;

    $scope.$apply();

    initControllerMemSlider();
    initControllerVcpuSlider();
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

            $('#openstackvmmemslider .ui-slider-range').removeClass('red');
            var color = '#007AFF';
            if (value < $scope.suggestedOpenStackVMMem) {
                color = '#BC1D2C';
                $('#openstackvmmemslider .ui-slider-range').addClass('red');
            }
            $('#openstackvmmemslider .ui-slider-range-min').css('background-color', color);
        }
    });

    $("#openstackvmmem").val(
      $("#openstackvmmemslider").slider("value").toString() + "MB");
}

function initControllerVcpuSlider() {

    var $scope = angular.element("#maindiv").scope();
    $("#openstackvmcpuslider").slider({
        range: "min",
        value: $scope.openStackVMCpu,
        min: $scope.minOpenStackVMCpu,
        max: $scope.maxOpenStackVMCpu,
        slide: function(event, ui) {
            var value = ui.value.toString();
            $("#openstackvmcpu").text(value);
            // AngularJs is not performing two way databinding
            $scope.openStackVMCpu = value;

            $('#openstackvmcpuslider .ui-slider-range').removeClass('red');
            var color = '#007AFF';
            if (value < $scope.suggestedOpenStackVMCpu) {
                color = '#BC1D2C';
                $('#openstackvmcpuslider .ui-slider-range').addClass('red');
            }
            $('#openstackvmcpuslider .ui-slider-range-min').css('background-color', color);

        }
    });

    $("#openstackvmcpu").val(
      $("#openstackvmcpuslider").slider("value").toString());
}

function initControllerNetworkingOptions() {
    $scope.useProxy = "yes";
}

function initHostNicsSelect() {
    $("#hostnics").selectmenu({
        change: function(event, ui) {
            // AngularJs two way databinding does not work
            // with selectmenu
            var value = $(this).val();
            console.log("Selected NIC: " + value);
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

function replaceDropdownIcon() {
    $('.ui-selectmenu-button').append('<i class="fa fa-sort" aria-hidden="true"></i>');
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

    $("#downloadmessagelater").click(function(){
        hidePage("#showDownload");
        return false;
    });

    $("#confirmmessageno").click(function(){
        hidePage("#showConfirm");
        return false;
    });

    $("#showError").keypress(function(event) {
        if ((event.which == 13) && ($("#showError").hasClass("error-visible"))) {
            hidePage("#showError");
        }
        return false;
    });

    $("#controllerconfignext").click(function(){
        if(validateConfigForm("#controllerconfigform")) {
            controller.validate_controller_config(
                JSON.stringify(getDeploymentConfigDict()))
        }
        $("#controllerconfigform .hide_validation").removeClass("hide_validation");
        return false;
    });

    $("#openstacknetworkingconfignext").click(function(){
        if(validateConfigForm("#openstacknetworkingconfigform")) {
            controller.validate_openstack_networking_config(
                JSON.stringify(getDeploymentConfigDict()));
        }
        $("#openstacknetworkingconfigform .hide_validation").removeClass("hide_validation");
        return false;
    });

    $("#openstacknetworkingconfigback").click(function(){
        controller.show_controller_config();
        return false;
    });

    $("#hostconfigback").click(function(){
        controller.show_openstack_networking_config();
        return false;
    });

    $("#hostconfignext").click(function(){
        if(validateHostConfigForm()) {
            controller.validate_host_config(
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

    $("#add-edit").click(function(){
        showMessage("Coming soon!", "This feature will be available in a forthcoming update!");
        return false;
    });

    $("#migrate").click(function(){
        controller.open_coriolis_url();
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

    $('#opengithuburlbutton1,#opengithuburlbutton2, .opengithuburlbutton').click(function(){
        controller.open_github_url();
        return false;
    });

    $('.openissuesurlbutton').click(function(){
        controller.open_issues_url();
        return false;
    });

    $('.openquestionsurlbutton').click(function(){
        controller.open_questions_url();
        return false;
    });

    $('#showdownloadbutton').click(function(){
        controller.open_download_url();
        return false;
    });

    $('#showhorizonbutton, #showhorizonbutton2').click(function(){
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

    $('#followtwitter').click(function() {
        // controller action here
        return false;
    })

    setPasswordValidation();
    initControllerMemSlider();
    initControllerVcpuSlider();

    $("#selectdistro").selectmenu();
    initRepoUrlSelect();
    initExtVSwitchSelect();
    initHostNicsSelect();

    setupTerm();

    replaceDropdownIcon();
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

function validateConfigForm(id) {
    if(!$(id)[0].checkValidity()) {
        showMessage("OpenStack configuration",
          "Please provide all the required configuration values");
        return false;
    } else {
        var $scope = angular.element(id).scope();
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

        initUi();

        tooltips();

        validations();

        controller.on_show_welcome_event.connect(showWelcome);
        controller.on_show_eula_event.connect(showEula);
        controller.on_show_controller_config_event.connect(
          showControllerConfig);
        controller.on_controller_config_validated_event.connect(
            controllerConfigValidated);
        controller.on_openstack_networking_config_validated_event.connect(
            openStackNetworkingConfigValidated);
        controller.on_show_openstack_networking_config_event.connect(
          showOpenStackNetworkingConfig);
        controller.on_show_host_config_event.connect(showHostConfig);
        controller.on_show_review_config_event.connect(showReviewConfig);
        controller.on_show_deployment_details_event.connect(
          showDeploymentDetails);
        controller.on_get_compute_nodes_completed_event.connect(
          updateComputeNodesView);
        controller.on_host_config_validated_event.connect(hostConfigValidated);
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
