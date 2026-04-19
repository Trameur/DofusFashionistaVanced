function hashPassword(password) {
    return CryptoJS.SHA256('dofusfashionista' + password).toString();
}

function login(username, password) {
    var hash = hashPassword(password);
    $.post("/local_login/",
           {username: username, password: hash},
           function (data) {
                if (data === 'ok') {
                    location.reload();
                } else if (data === 'invalid') {
                    $("#incorrect-password-error").text(gettext("The username and password entered do not match."));
                } else if (data === 'confirm-email') {
                    $("#incorrect-password-error").text(gettext("Confirm your email to log in."));
                } else {
                    $("#incorrect-password-error").text(gettext("Error while logging in."));
                }
           });
}

function changePassword(username, password, newPassword){
    var hashPass = hashPassword(password);
    var hashNewPass = hashPassword(newPassword);
    $.post("/change_password/",
           {username: username, password: hashPass, newPassword: hashNewPass},
           function (data) {
                if (data === 'ok') {
                    $("#change-succesful").text(gettext("Your password has been changed."));
                    $("#wrong-password-error").empty();
                    $("#login-password").val("");
                    $("#password").val("");
                    $("#password-confirm").val("");
                } else {
                    $("#wrong-password-error").text(gettext("Your password did not match our records."));
                    $("#change-succesful").empty();
                }
           });
}

function validate_username() {
    var username = $("#register-username").val();
    $.post("/check_username/",
           {username: username},
           function (data) {
                if (data === 'username-error') {
                    $("#username-taken-error").text(gettext("This username is already in use."));
                    $("#login-register").attr('disabled','disabled');
                } else {
                    $("#username-taken-error").empty();
                    $("#login-register").removeAttr('disabled');
                }
           });
}

function validate_password() {
    var pw = $("#password");
    var pwCon = $("#password-confirm");
    if (pw.val() === pwCon.val() || pw.val() === "" || pwCon.val() ==="") {
        $("#password-error").empty();
        $("#login-register").removeAttr('disabled');
    } else {
        $("#password-error").text(gettext("The passwords don't match. Please try again."));
        $("#login-register").attr('disabled','disabled');
    }
}

function validateEmail(email) {
    var re = /\S+@\S+\.\S+/;
    return re.test(email);
}

function registerSubmit(e) {
    var username = $("#register-username").val();
    var password = $("#password").val();
    var email = $("#email").val();
    
    var failed = false;
    if (username === "" || $("#username-taken-error").text() != "") {
        failed = true;
        $("#username-taken-error").text(gettext("You need to enter a valid username."));
    } else {
        $("#username-taken-error").empty();
    }
    if (password === "") {
        failed = true;
        $("#password-error").text(gettext("You need to enter a password."));
    } else {
        $("#password-error").empty();
    }
    if (email === "" || email.indexOf("@") < 1 || email.indexOf(".") < 3) {
        failed = true;
        $("#email-error").text(gettext("You need to enter a valid email."));
    } else {
        $("#email-error").empty();
    }
    
    if (!failed) {
        var hash = hashPassword(password);
        $("#password-actual").val(hash);
    } else {
        e.preventDefault();
    }
}

