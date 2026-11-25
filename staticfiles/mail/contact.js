$(function () {

    $("#contactForm input, #contactForm textarea").jqBootstrapValidation({
        preventSubmit: true,
        submitError: function ($form, event, errors) {
        },
        submitSuccess: function ($form, event) {
            event.preventDefault();
            var name = $("input#name").val().trim();
            var email = $("input#email").val().trim();
            var subject = $("input#subject").val().trim();
            var message = $("textarea#message").val().trim();
            var csrfToken = $("input[name='csrfmiddlewaretoken']").val();
            var postUrl = $("#contactForm").attr("action") || window.location.pathname;

            var $this = $("#sendMessageButton");
            var originalText = $this.text();
            $this.prop("disabled", true).html('<i class="fa fa-spinner fa-spin mr-1"></i>Sending...');

            $.ajax({
                url: postUrl,
                type: "POST",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                data: {
                    csrfmiddlewaretoken: csrfToken,
                    is_ajax: "true",
                    name: name,
                    email: email,
                    subject: subject,
                    message: message
                },
                cache: false,
                success: function (response) {
                    var successMessage = (response && response.message) ? response.message : "Your message has been sent successfully!";
                    $('#success').html("<div class='alert alert-success alert-dismissible fade show shadow-sm' role='alert'>");
                    $('#success > .alert-success')
                        .html("<i class='fa fa-check-circle mr-2'></i><strong>" + successMessage + "</strong>")
                        .append("<button type='button' class='close' data-dismiss='alert' aria-label='Close'><span aria-hidden='true'>&times;</span></button>");
                    $('#contactForm').trigger("reset");

                    // Auto-dismiss after 4 seconds
                    setTimeout(function () {
                        $('#success .alert').fadeTo(500, 0).slideUp(500, function () {
                            $(this).remove();
                        });
                    }, 4000);
                },
                error: function (xhr) {
                    var errorMsg = "Sorry " + name + ", it seems our mail server is not responding. Please try again later!";
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        errorMsg = xhr.responseJSON.message;
                    }
                    $('#success').html("<div class='alert alert-danger alert-dismissible fade show shadow-sm' role='alert'>");
                    $('#success > .alert-danger')
                        .html("<i class='fa fa-exclamation-circle mr-2'></i><strong>" + errorMsg + "</strong>")
                        .append("<button type='button' class='close' data-dismiss='alert' aria-label='Close'><span aria-hidden='true'>&times;</span></button>");

                    // Auto-dismiss after 4 seconds
                    setTimeout(function () {
                        $('#success .alert').fadeTo(500, 0).slideUp(500, function () {
                            $(this).remove();
                        });
                    }, 4000);
                },
                complete: function () {
                    setTimeout(function () {
                        $this.prop("disabled", false).text(originalText);
                    }, 800);
                }
            });
        },
        filter: function () {
            return $(this).is(":visible");
        },
    });

    $("a[data-toggle=\"tab\"]").click(function (e) {
        e.preventDefault();
        $(this).tab("show");
    });
});

$('#name').focus(function () {
    $('#success').html('');
});
