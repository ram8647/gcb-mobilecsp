

/**
 * functions to rebuild completion column based off of selected unit
 */
function rebuildCompletionColumn(students, unitSelect, lessonSelect) {
    var unitId = $(unitSelect).val();
    var lessonId = $(lessonSelect).val();
    $('.student-list-table > tbody > tr').each(function(index, value) {
        var completionValue;
        var lessonCompletionValue;
        var lessonScore;
        var studentId = $(this).find('.student-id').val();
        var student;

        $.each(students, function (sKey, s) {
            if (s.email === studentId) {
                student = s;
            }
        });

        if (student === undefined) {
            return;
        }

        if (unitId != 'course_completion') {
            completionValue = student.unit_completion[unitId] * 100;
            for (var i = 0; i < student.detailed_course_completion.length; i++) {
                var unit_detail = student.detailed_course_completion[i];
                if (unit_detail.unit_id == unitId) {
                    for (var j = 0; j < unit_detail.lessons.length; j++) {
                        if (unit_detail.lessons[j].lesson_id == lessonId) {
                            lessonCompletionValue = CalculateLessonCompletion(studentId, unitId, lessonId, window
                                .scores);
                            lessonScore = CalculateLessonScore(studentId, unitId, lessonId, window.scores);
                        }
                    }
                }
            }
        }
        else {
            completionValue = student.course_completion;
            lessonCompletionValue = 'N/A';
        }

        $(this).find('.student-progress').val(completionValue / 100);
        $(this).find('.student-progress').append('<div class="progress-bar">' +
            '<span style="width:' + completionValue / 100 + '%;">Progress: ' + completionValue + '%</span>' +
            '</div>');
        $(this).find('.student-completion-value').text(completionValue.toPrecision(4) + '%');

        if (lessonCompletionValue == 'N/A') {
            $(this).find('.student-lesson-completion > .student-lesson-completion-percentage').text
                (lessonCompletionValue);
            $(this).find('.student-lesson-completion > .student-lesson-completion-score').text('');
        }
        else {
            $(this).find('.student-lesson-completion > .student-lesson-completion-percentage').text(lessonCompletionValue + '%');
            if (lessonScore) {
                $(this).find('.student-lesson-completion > .student-lesson-completion-score').text('Score: '
                + lessonScore.total + '/' + lessonScore.possible);
            }
        }
    });
}

/**
 * Adding function to global scope for use in section list view
 */
window.RebuildCompletionColumn = rebuildCompletionColumn;