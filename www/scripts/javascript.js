function showOne(id) {
       $('.hyperv').hide();
         $('#'+id).show();
}

function showPassword(x){
   x.type = "text";
}
function hidePassword(x){
  x.type = "password";
}