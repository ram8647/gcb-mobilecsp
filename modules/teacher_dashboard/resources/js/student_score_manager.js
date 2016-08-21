
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

/**
 *  Creates an array of question attempts for a given lesson.
 *  @param questions, the questions associated with the lesson.
 *  @param attempts, a dict of the questions attempted by the student
 *  @return An n x 3 array, containing [id, #attempts, score] for each
 *   of the n questions in the lesson. 
 */
function createQuestionsAttemptsArray(questions, attempts) {
    var question_attempts = [];
    $.each(questions, function (key, value) {
        var id = value['question_id'];
        var score = value['weighted_score'];
        if (id in attempts) {
	  question_attempts.push([id, attempts[id], score]);
	} else {
	  question_attempts.push([id, 0, 0]);
	}
    });
    return question_attempts;;
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

window.GetQuestionScoresForStudentByLesson = getQuestionScoresForStudentByLesson;
window.CreateQuestionsAttemptsArray = createQuestionsAttemptsArray;
window.CalculateLessonScore = calculateLessonScore;
window.CalculateLessonCompletion = calculateLessonCompletion;
