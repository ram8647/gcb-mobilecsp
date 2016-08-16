/**
 * This file contains the classes to manage Student Detail Mapping widgets.
 *  Modified version of the skill_tagging_lib.js
 */

var STUDENT_DETAIL_API_VERSION = '1';
var ESC_KEY = 27;
var MAX_STUDENT_DETAIL_REQUEST_SIZE = 10;

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
 * A student detail table builder.
 *
 * @class
 */
function StudentDetailTable(unitList) {
  this._unitList = unitList;
}

StudentDetailTable.prototype = {
  _buildRow: function(unit) {
    var tr = $('<tr class="row ' + unit.unit_id + '"></tr>');
    tr.click(function() {
      var unitId = $(this).find('.unit-title').data('unit_id');
      var lesson_class = '.' + unitId + '-lesson';

      $('.' + unitId + '-lessons').slideToggle('fast', function () {
      if (!$('.' + unitId + '-lessons').is(':visible')) {
        $('#questions-container').empty();
      }
      else {
        $('.' + unitId + '-lessons').each(function () {
          var lessonId = $(this).find('.lesson-id').text();

          var lessonScores = retrieveLessonScores(window.scores, unitId, lessonId);

          var activityTable = new ActivityTable(lessonScores);
          var table = activityTable.buildTable(
            unitId,
            lessonId,
            $('.' + unitId).find('.unit-title').text(),
            $(this).find('.lesson-title').text()).appendTo('#questions-container');

            var lessonScore = CalculateLessonScore(window.studentEmail,
              unitId,
              lessonId,
              window.scores);
            var lessonCompletion = CalculateLessonCompletion(window.studentEmail,
              unitId,
              lessonId,
              window.scores);

            $(this).find('.lesson-completion').text(lessonCompletion + '% answered | Score: ' +
              lessonScore.total + '/' + lessonScore.possible);
          });
        }
      });
    });

    // add unit/lesson name
    var td = $(
        '<th class="unit-title" style="cursor:pointer;color:blue">' +
        '  <span class="unit">' +
        '</th>'
    );
    td.text(unit.title);
    td.data('unit_id', unit.unit_id);
    tr.append(td);

    // add completion
    td = $(
        '<td class="unit-completion-' + unit.unit_id + '">' +
        '</td>'
    );

    td.text(unit.completion * 100 + '%');
    tr.append(td);

    return tr;
  },

  _buildSubRow: function(lesson, unit_id) {
    var tr = $('<tr class="row ' + unit_id + '-lessons ' + lesson.lesson_id + '-lesson lesson" style="display: none;' +
      '"></tr>');

    // add unit/lesson name
    var td = $(
        '<th class="lesson-title">' +
        '</th>'
    );
    td.text(lesson.title);
    tr.append(td);

    // add unit/lesson id
    var td = $(
        '<th class="lesson-id" style="display: none;">' +
        '</th>'
    );
    td.text(lesson.lesson_id);
    tr.append(td);

    // add score
    td = $(
        '<td class="lesson-completion" id="lesson-completion-' + unit_id + '">' +
        '</td>'
    );

    td.text(lesson.completion / 2 * 100 + '%');
    tr.append(td);

    return tr;
  },

  _unitsCount: function() {
    var that = this;
    return Object.keys(that._unitList._unitLookupByIdTable).length;
  },

  _buildHeader: function() {
    var that = this;
    var thead = $(
      '<thead>' +
      '  <tr>' +
      '    <th class="unit">Unit <span class="unit-count"></span></th>' +
      '    <th class="score">Year</th>' +
      '  </tr>' +
      '</thead>'
    );
    thead.find('.unit-count').text('(' + that._unitsCount() + ')')
    return thead;
  },

  _buildBody: function() {
    var that = this;
    var tbody = $('<tbody></tbody>');

    var i = 0;
    that._unitList.eachUnit(function(unit) {
      var row = that._buildRow(unit);
      //row.addClass( i++ % 2 == 0 ? 'even' : 'odd');
      tbody.append(row);

      for (var j = 0; j < unit.lessons.length; j++)  {
        var row = that._buildSubRow(unit.lessons[j], unit.unit_id);
        row.addClass(i++ % 2 == 0 ? 'even' : 'odd');
        tbody.append(row);
      }
    });

    return tbody;
  },

  _refresh: function() {
    this._table.find('tbody').remove();
    this._table.append(this._buildBody());
  },

  buildTable: function() {
    var that = this;

    this._content = $(
      '<h3>Student Detail Table</h3>' +
      '<table class="units-table"></table>');

    this._table = this._content.filter('table.units-table');
    this._table.append(that._buildHeader());

    this._refresh();

    return this._content;
  }
};


/**
 * A proxy to load and work with a list of unit progress from the server. Each of the
 * units is an object with fields for ....
 *
 * @class
 */
function UnitList() {
  this._unitLookupByIdTable = {};
  this._studentName = '';
  this._studentEmail = '';
  this._xsrfToken = null;
}

UnitList.prototype = {
  /**
   * Load the unit list from the server.
   *
   * @method
   * @param callback {function} A zero-args callback which is called when the
   *     unit list has been loaded.
   */
  load: function(callback, param) {
    var that = this;
    $.ajax({
      type: 'GET',
      url: 'rest/modules/teacher_dashboard/student_progress',
      data: {'student': param},
      dataType: 'text',
      success: function(data) {
        that._onLoad(callback, data);
      },
      error: function(error) {
        showMsg('Can\'t load the student progress.');
      }
    });
  },

  /**
   * @param id {string}
   * @return {object} The unit with given id, or null if no match.
   */
  getUnitById: function(id) {
    return this._unitLookupByIdTable[id];
  },

  /**
   * @return {string} The student name
   */
   getStudentName: function () {
    return this._studentName;
   },

   /**
   * @return {string} The student email
   */
   getStudentEmail: function () {
    return this._studentEmail;
   },

  /**
   * Iterate over the unit in the list.
   *
   * @param callback {function} A function taking a unit as its arg.
   */
  eachUnit: function(callback) {
    for (var prop in this._unitLookupByIdTable) {
      if (this._unitLookupByIdTable.hasOwnProperty(prop)) {
        callback(this._unitLookupByIdTable[prop]);
      }
    }
  },

  _onLoad: function(callback, data) {
    data = parseAjaxResponse(data);
    if (data.status != 200) {
      showMsg(data.message);
      return;
    }
    this._xsrfToken = data['xsrf_token'];
    var payload = JSON.parse(data['payload']);
    this._updateFromPayload(payload);

    if (callback) {
      callback();
    }
  },

  _updateFromPayload: function(payload) {
    var that = this;
    var unitList = payload['units'];
    that._studentName = payload.student_name;
    that._studentEmail = payload.student_email;

    this._unitLookupByIdTable = [];
    $.each(unitList, function() {
      that._unitLookupByIdTable[this.unit_id] = this;
    });
  },
};


window.UnitList = UnitList;
window.StudentDetailTable = StudentDetailTable;