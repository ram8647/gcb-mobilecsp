var ESC_KEY = 27;

/**
 * An activity scores table builder.
 *
 * @class
 */
function ActivityTable(activityScores) {
  this._activityScores = activityScores;
}

function openModal() {
  // Bind Esc press to close window
  $(document).on("keyup.modal", function(e) {
    if (e.keyCode == ESC_KEY) {
        closeModal();
    }
  });
  $("#question-window").show();
}

function closeModal() {
  $("#question-window, #question-container > div").hide();
  //Remove Esc binding
  $(document).off("keyup.modal");
}

/**
 * Sets up handlers for modal window.
 */
function setUpModalWindow() {
  // Bind click on background and on close button to close window
  $("#question-background, #question-window .question-close-button").on("click", function(e) {
    closeModal();
  });
  $("#question-container > div").hide();
}

ActivityTable.prototype = {
  _buildRow: function(sequence, question) {

    var tr = $('<tr class="row"></tr>');

    // add question number
    var td = $(
        '<td class="question-info">' +
        '  Question ' + ++sequence +
        ' <div class="icon md md-visibility"></div>' +
        '</td>'
    );
    td.find('.md-visibility').data('quid', question[0]['quid']);

    tr.append(td);

    td.find('.md-visibility').click(function () {
      openModal();
      var params = {
          action: 'question_preview',
          quid: $(this).data('quid')
      };
      $('#question-preview').html($('<iframe />').attr(
        {id: 'question-preview', src: 'dashboard?' + $.param(params)})).show();
    });

    // add choices
    var numOfColumns = this._columnCount();
    var numCorrect = 0;
    var numIncorrect = 0;

    for (var i = 1; i <= numOfColumns; i++) {
      var td;

      if (i <= question.length) {
        var td = $(
          '<td class="choice-info-' + i + '">' +
            question[i-1].count +
          '</td>'
        );

        if (question[i-1].score > 0) {
          $(td).addClass('correct-choice');
          numCorrect += question[i-1].count;
        }
        else {
          numIncorrect += question[i-1].count;
        }
      }
      else {
        var td = $(
          '<td class="choice-info-' + i + '">--</td>'
        );
      }

      tr.append(td);
    }

    var totalQuestions = numCorrect + numIncorrect;
    var percentCorrect = 0;
    if (totalQuestions > 0) {
        percentCorrect = numCorrect / totalQuestions;
    }

    if (percentCorrect < .75 && percentCorrect > .5) {
      $($(tr).find('.question-info')).addClass('uncertain-question');
    }
    else if (percentCorrect <= .5) {
      $($(tr).find('.question-info')).addClass('problem-question');
    }

    return tr;
  },

  _buildHeader: function() {
    var numOfColumns = this._columnCount();

    var thead = $(
      '<thead>' +
      '  <tr>' +
      '    <th></th>' +
      '  </tr>' +
      '</thead>'
    );

    for (var i = 1; i <= numOfColumns; i++) {
      $(thead).find('tr').append('<th> Choice ' + i + '</th>');
    }

    return thead;
  },

  _buildBody: function() {
    var that = this;
    var tbody = $('<tbody></tbody>');

    var i = 0;
    $.each(that._activityScores, function (key, question) {
      var row = that._buildRow(key, question);
      row.addClass( i++ % 2 == 0 ? 'even' : 'odd');
      tbody.append(row);
    });

    return tbody;
  },

  _refresh: function() {
    this._table.find('tbody').remove();
    this._table.append(this._buildBody());
  },

  _columnCount: function() {
    var numOfColumns = 0;
    $.each(this._activityScores, function (key, question) {
      if (numOfColumns === 0 || question.length > numOfColumns) {
        numOfColumns = question.length;
      }
    });

    return numOfColumns;
  },

  buildTable: function(unitId, lessonId, unitTitle, lessonTitle) {
    var that = this;

    this._content = $(
      '<div class="info" style="margin: 10px;">' +
      '<h3>Question Scores for Unit: ' + unitTitle + ', Lesson: ' + lessonTitle + '</h3>' +
      '<table class="questions-table"></table>');

    this._table = this._content.find('.questions-table');
    this._table.append(that._buildHeader());

    this._refresh();

    return this._content;
  }
};

function retrieveLessonScores(scores, unitId, lessonId) {
  var lessonScores = {};

  $.each(scores, function (studentId, units) {
    var questions = units[unitId][lessonId];
    $.each(questions, function (sequence, question) {
      if (!lessonScores[sequence]) {
        $.each(question['choices'], function (key, value) {
          value.count = 0;
          value.quid = question['question_id']
        });
        lessonScores[sequence] = question['choices'];
      }
      $.each(question['answers'], function (key, value) {
        if (question['question_type'] === 'SaQuestion') {
          var weighted_score = question['weighted_score'];
          if (weighted_score > 0) {
            lessonScores[sequence][0].count += 1;
          }
          else {
            if (lessonScores[sequence][1] === undefined) {
              lessonScores[sequence][1] = lessonScores[sequence][0];
              lessonScores[sequence][1].count = 0;
            }
            lessonScores[sequence][1].count += 1;
          }
          return;
        }
        else {
          lessonScores[sequence][value].count += 1;
        }
      });
    });
  });

  return lessonScores;
}


window.retrieveLessonScores = retrieveLessonScores;
window.ActivityTable = ActivityTable;

setUpModalWindow();