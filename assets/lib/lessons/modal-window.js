    /**
     * Sets up handlers for the modal window that displays the quiz questions.
     *
     * How this works: Quiz previews are displayed using the GCB dashboard module.  
     * They use the template:  modules/dashboard/templates/question_preview.html and
     *  and require the style sheet:  assets/lib/lessons/question_preview.css.
     *  They script in question_preview requires that the iframe containing the
     *  preview be contained in a window named modal-window.  See the HTML code
     *  at the very bottom of this file.
     */
    var ESC_KEY = 27;

    function setUpModalWindow() {
      // Bind click on background and on close button to close window
      $("#question-background, #modal-window .question-close-button").on("click", function(e) {
	closeModal();
      });
      $("#question-container > div").hide();
    }

    function openModal() {
      // Bind Esc press to close window
      $(document).on("keyup.modal", function(e) {
	if (e.keyCode == ESC_KEY) {
	    closeModal();
	}
      });
      $("#modal-window").show();
    }

    function closeModal() {
      $("#modal-window, #question-container > div").hide();
      //Remove Esc binding
      $(document).off("keyup.modal");
    }
