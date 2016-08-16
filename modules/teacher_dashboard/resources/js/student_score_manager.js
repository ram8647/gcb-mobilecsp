
/**
 * function to calculate a students scores for a lesson
 */
function calculateLessonScore(studentId, unitId, lessonId, scores) {

    var lessonScore = {
        possible: 0, total: 0
    };

    var questions = getQuestionScoresForStudentByLesson(studentId, unitId, lessonId, scores);

    $.each(questions, function (key, value) {
        lessonScore.total += value['weighted_score'];
        lessonScore.possible += value['possible_points'];
    });

    return lessonScore;
}

/**
 * function to calculate lesson completion for a student
 */
function calculateLessonCompletion(studentId, unitId, lessonId, scores) {
    var completedQuestions = 0;
    var totalQuestions = 0;

    var questions = getQuestionScoresForStudentByLesson(studentId, unitId, lessonId, scores);

    $.each(questions, function (key, value) {
        if (value['question_type'] !== 'NotCompleted') {
            completedQuestions = completedQuestions + 1;
        }

        totalQuestions = totalQuestions + 1;
    });

    var completionPercent = 0;
    if (totalQuestions > 0) {
        completionPercent = (completedQuestions / totalQuestions) * 100;
    }

    return completionPercent;
}

function getQuestionScoresForStudentByLesson(studentId, unitId, lessonId, scores) {
    var questions = [];

    if (scores && scores[studentId]) {
        if (scores[studentId][unitId]) {
            if (scores[studentId][unitId][lessonId]) {
                questions = scores[studentId][unitId][lessonId];
            }
        }
    }

    return questions;
}

window.CalculateLessonScore = calculateLessonScore;
window.CalculateLessonCompletion = calculateLessonCompletion;
