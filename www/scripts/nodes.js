// var hostnames = new Array;
// var usernames = new Array;
// var passwords = new Array;
// var n = 0;

// function readData(){
// 	var hostname = document.getElementById('hostname').value;
// 	hostnames.push(hostname);
// 	var username = document.getElementById('username').value;
// 	usernames.push(username);
// 	var passwords = document.getElementById('password').value;
// 	password.push(password);
// 	n++;
// }

// $("button#submit-configform").click(function() {
// 	for (var i = 1; i <= n; i++) {
//     	var new_list = "<ul><li>" + hostname[i] + "</li><li>" + username[i] + "</li><li>" hostname[i] + "</li></ul>";
//     }
//     $("compute-nodes-list").append(new_list);
//     return false;
// });


$("button#submit-configform").click(function() {
	var hostname = document.getElementById('hostname').value;
	var username = document.getElementById('username').value;
	var passwords = document.getElementById('password').value;
    var new_list = "<ul><li>" + hostname + "</li><li>" + username + "</li><li>" hostname + "</li></ul>";
 	var div = document.getElementById('test1');
    div.innerHTML = div.innerHTML + "<ul><li>" + hostname + "</li><li>" + username + "</li><li>" hostname + "</li></ul>";

    $("compute-nodes-list").append(new_list);
    return false;
});