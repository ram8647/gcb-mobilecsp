/**
 * This file contains the classes to manage Section Mapping widgets.
 *  Modified version of the skill_tagging_lib.js
 */

var SECTION_API_VERSION = '1';
var ESC_KEY = 27;
var MAX_SECTION_REQUEST_SIZE = 10;

/*********************** Start Dependencies ***********************************/
// The following symols are required to be defined in the global scope:
//   cbShowMsg, cbShowMsgAutoHide
var showMsg = cbShowMsg;
var showMsgAutoHide = cbShowMsgAutoHide;
/************************ End Dependencies ************************************/

function parseAjaxResponse(s) {
  // XSSI prefix. Must be kept in sync with models/transforms.py.
  var xssiPrefix = ")]}'";
  return JSON.parse(s.replace(xssiPrefix, ''));
}

/**
 * InputEx adds a JSON prettifier to Array and Object. This works fine for
 * InputEx code but breaks some library code (e.g., jQuery.ajax). Use this
 * to wrap a function which should be called with the InputEx extras turned
 * off.
 *
 * @param f {function} A zero-args function executed with prettifier removed.
 */
function withInputExFunctionsRemoved(f) {
  var oldArrayToPrettyJsonString = Array.prototype.toPrettyJSONString;
  var oldObjectToPrettyJsonString = Object.prototype.toPrettyJSONString;
  delete Array.prototype.toPrettyJSONString;
  delete Object.prototype.toPrettyJSONString;

  try {
    f();
  } finally {
    if (oldArrayToPrettyJsonString !== undefined) {
      Array.prototype.toPrettyJSONString = oldArrayToPrettyJsonString;
    }
    if (oldObjectToPrettyJsonString !== undefined) {
      Object.prototype.toPrettyJSONString = oldObjectToPrettyJsonString;
    }
  }
}

/**
 * A class to put up a modal lightbox. Use setContent to set the DOM element
 * displayed in the lightbox.
 *
 * @class
 */
function Lightbox() {
  this._window = $(window);
  this._container = $('<div class="lightbox"/>');
  this._background = $('<div class="background"/>');
  this._content = $('<div class="content"/>');

  this._container.append(this._background);
  this._container.append(this._content);
  this._container.hide();
}
Lightbox.prototype = {
  /**
   * Set a DOM element to root the lightbox in. Typically will be document.body.
   *
   * @param rootEl {Node}
   */
  bindTo: function(rootEl) {
    $(rootEl).append(this._container);
    return this;
  },
  /**
   * Show the lightbox to the user.
   */
  show: function() {
    this._container.show();
    var top = this._window.scrollTop() +
        Math.max(8, (this._window.height() - this._content.height()) / 2);
    var left = this._window.scrollLeft() +
        Math.max(8, (this._window.width() - this._content.width()) / 2);

    this._content.css('top', top).css('left', left);
    return this;
  },
  /**
   * Close the lightbox and remove it from the DOM.
   */
  close: function() {
    this._container.remove();
    return this;
  },
  /**
   * Set the content shown in the lightbox.
   *
   * @param contentEl {Node or jQuery}
   */
  setContent: function(contentEl) {
    this._content.empty().append(contentEl);
    return this;
  }
};


/**
 * A modal popup to add students.
 *
 * @class
 * @param sectionId {string}
 */
function EditStudentsPopup(sectionId, xsrfToken, action) {
  var that = this;
  this._action = action;
  this._sectionId = sectionId;
  this._xsrfToken = xsrfToken;
  this._documentBody = $(document.body);
  this._lightbox = new Lightbox();
  var titleText = (action) ? 'Add' : 'Delete';

  this._form = $(
      '<div class="add-students-popup">' +
      '  <h2 style="text-align: center; margin-left: 0px;" class="title">' + titleText + ' Students</h2>' +
      '  <div class="form-row">' +
      '    <label style="vertical-align: top; margin-left: 8px; margin-bottom: 5px;">Students</label><br />' +
      '    <textarea style="margin: 8px;" class="student-emails" rows="5"' +
      '        placeholder="Enter student emails seperated by commas."></textarea>' +
      '  </div>' +
      '  <div class="controls" style="text-align: center">' +
      '    <button class="gcb-button students-save-button">Save</button>' +
      '    <button class="gcb-button students-cancel-button">Cancel</button>' +
      '  </div>' +
      '</div>');

  this._emailInput = this._form.find('.student-emails');

  this._form.find('button.students-save-button').click(function() {
    cbShowMsg('Saving...');
    that._onSave(that._action);
    return false;
  });

  this._form.find('button.students-cancel-button')
    .click(function() {
      that._onCancel();
      return false;
    }
  );
}

EditStudentsPopup.prototype = {
  /**
   * Display the popup to the user.
   *
   * @param callback {function} Called with the new section after students for a section are
   *     edited. The section is automatically added to the student list, so there is
   *     no need to update the list in the callback.
   */
  open: function(callback) {
    this._onAjaxEditStudentCallback = callback;
    this._lightbox
      .bindTo(this._documentBody)
      .setContent(this._form)
      .show();
    $('.student-emails').focus();

    var that = this;
    $(document).on('keydown', function(e) {
      if (e.which == ESC_KEY) {
        that._lightbox.close();
        $(document).unbind('keydown');
      }
    });

    return this;
  },

  rebuildStudentsTable(students, table) {

    table.remove('tbody');
    var tbody = $('<tbody></tbody>');

    for (var key in students) {
        var student = students[key];

        var tr = $('<tr></tr>');

        var td = $(
            '<td>' +
            '  <a class="gcb-button" role="button"' +
            '      href="/' + window.course_namespace +
            '/modules/teacher_dashboard?action=teacher_dashboard&tab=student_detail&student=' +
            student.email + '">View Dashboard</a>' +
            '</td>'
        );
        tr.append(td);

        td = $(
            '<td>' +
            '  <span class="student-name"></span>' +
            '</td>'
        );

        td.find('.student-name').text(student.name);
        tr.append(td);

        td = $(
            '<td>' +
            '  <span class="student-email"></span>' +
            '</td>'
        );

        td.find('.student-email').text(student.email);
        tr.append(td);

        var completionValue = student.course_completion;
        var lessonCompletionValue = 'N/A';

        td = $(
            '<td>' +
            '   <progress class="student-progress" value="' + (completionValue / 100) + '">' +
            '   <div class="progress-bar">' +
            '     <span style="width:' + (completionValue / 100) + '%;">Progress:' + completionValue/100 + '</span>' +
            '   </div>' +
            '   </progress>' +
            '   <span class="student-completion">' + completionValue + '%</span>' +
            '</td>'
        );

        tr.append(td);

        td = $(
            '<td class="student-lesson-completion">' +
            '  <span class="student-lesson-completion-percentage">' + lessonCompletionValue + '</span>' +
            '  <span class="student-lesson-completion-score"></span>' +
            '</td>'
        );

        tr.append(td);

        td = $('<td style="display:none;">' +
          '<input  class="student-id" type="hidden" value="' + student.email + '"' +
          '/></td>'
        );

        tr.append(td);

        tbody.append(tr);
    }

    table.append(tbody);
  },

  _onSave: function(action) {
    var that = this;
    var emails = this._emailInput.val();

    function onUpdatedStudents(student_list, message) {
      showMsgAutoHide(message);
      that._onAjaxEditStudentCallback(student_list);
    }
    this.updateStudents(onUpdatedStudents, emails, that._sectionId, that._xsrfToken, (action) ? 'insert' : 'delete');
    this._lightbox.close();
  },

  _onCancel: function() {
    this._lightbox.close();
  },

  /**
   * Add students and store them on the server.
   *
   * @param callback {function} A callback which takes (student_list, message) args
   * @param emails {string}
   * @param sectionId
   */
  updateStudents: function(callback, emails, sectionId, xsrfToken, action) {

    var that = this;

    if (! emails) {
      showMsg('Email list can\'t be empty');
      return;
    }

    var requestDict = {
      xsrf_token: xsrfToken,
      key: sectionId,
      payload: JSON.stringify({
        'version': SECTION_API_VERSION,
        'name': null,
        'description': null,
        'active': null,
        'students': {
            emails: emails,
            action: action
         },
        'year': null
      })
    };

    var request = JSON.stringify(requestDict);

    withInputExFunctionsRemoved(function() {
      $.ajax({
        type: 'PUT',
        url: 'rest/modules/teacher_dashboard/section',
        data: {'request': request},
        dataType: 'text',
        success: function(data) {
          data = parseAjaxResponse(data);
          if  (data.status != 200) {
            showMsg(data.message);
            return;
          }
          var payload = JSON.parse(data.payload);
          //this._updateFromPayload(payload);

          if (callback) {
            callback(payload.section.students, data.message);
          }
        }
      });
    });
  }
};

function SectionEditorForOeditor(env) {
  var that = this;

  this._env = env;
  this._sectionList = new SectionList();

  var newSectionDiv = $('<div class="new-section"></div>');
  var newSectionButton = $('<button class="add">+ Create New section</button>');
  newSectionButton.click(function() {
    new EditSectionPopup(that._sectionList, null, null).open(function(section) {
      that._onSectionsSelectedCallback([section.id]);
      that._populatePrereqSelector();
    });
    return false;
  });
  newSectionDiv.append(newSectionButton);

  this._sectionWidgetDiv = $('<div class="inputEx-Field"></div>');
  this._sectionWidgetDiv.append(this._prereqDisplay.element());

  var buttonDiv = $('<div class="section-buttons"></div>');
  this._sectionWidgetDiv.append(buttonDiv);
  buttonDiv.append(newSectionDiv);
}

SectionEditorForOeditor.prototype = {
  element: function() {
    return this._sectionWidgetDiv;
  },
  init: function() {
    var that = this;
    this._sectionList.load(function() {
      that._populateSectionList();
    });
  },
  _onSectionsSelectedCallback: function(selectedSectionIds) {
    // When new sections are selected in the SectionSelector, update the OEditor
    // form and repopulate the SectionDisplay.
    var that = this;
    $.each(selectedSectionIds, function() {
      if (! that._formContainsSectionId(this)) {
        that._env.form.inputsNames.sections.addElement({'section': this});
      }
    });
    this._populateSectionList();
  },
  _onRemoveCallback: function (sectionId) {
    // When a section is removed from the SectionDisplay, also remove it from the
    // OEditor form.
    var that = this;
    $.each(this._env.form.inputsNames.sections.subFields, function(i) {
      var id = this.inputsNames.section.getValue();
      if (id === sectionId) {
        that._env.form.inputsNames.sections.removeElement(i);
        return false;
      }
    });
  },
  _populateSectionList: function() {
    // Populate the SectionDisplay with the sections in the OEditor form.
    var that = this;
    $.each(this._env.form.inputsNames.sections.subFields, function() {
      var id = this.inputsNames.section.getValue();
      var section = that._sectionList.getSectionById(id);
    });
  },
  _formContainsSectionId: function(sectionId) {
    var fields = this._env.form.inputsNames.sections.subFields;
    for(var i = 0; i < fields.length; i++) {
      var id = fields[i].inputsNames.section.getValue();
      if (sectionId.toString() === id.toString()) {
        return true;
      }
    }
    return false;
  }
};

/**
 * Export the classes which will be used in global scope.
 */
window.SectionEditorForOeditor = SectionEditorForOeditor;
window.SectionList = SectionList;
window.SectionTable = SectionTable;
window.EditStudentsPopup = EditStudentsPopup;

