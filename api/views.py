import json

from django.core import serializers
from django.db.models import Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_list_or_404, get_object_or_404
from engine import utils
from engine.models import *
from ltilib.utils import grade_passback
from numpy import std
from rest_framework import viewsets

from api.serializers import *

##########################
##### rest-framework #####
##########################


class QuizViewSet(viewsets.ModelViewSet):
    """
    list quizzes
    """

    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer


class QuestionViewSet(viewsets.ModelViewSet):
    """
    list questions
    """

    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


#####################################################################
#### custom endpoints, used by qualtrics to retrieve object text ####
#####################################################################


def get_question(request):
    """
    INPUT (via GET params): question_id
    OUTPUT: quiz_id, question_text, correct_choice, [answer{n}_text]*n
    """
    if "id" not in request.GET:
        return HttpResponse("question_id not found in GET parameters")
    question = get_object_or_404(Question, pk=request.GET["id"])
    answers = question.answer_set.order_by("_order")

    num_answers = len(answers)

    # identifies the correct answer choice
    # if there's more than one labelled correct only the first is identified
    correct_choice = 0
    for i in range(num_answers):
        if answers[i].correct:
            correct_choice = i + 1
            break

    output = {
        "text": question.text,
        "correct_choice": correct_choice,
    }

    # add answer text to output, e.g. answer1_text: "answer text"
    for i in range(num_answers):
        output["answer{}_text".format(i + 1)] = answers[i].text

    return JsonResponse(output, json_dumps_params={"sort_keys": True})


def is_correct(request):
    """
    to be implemented if useful
    check whether a answer is correct or not
    """
    pass


def get_explanation_for_student(request):
    """
    Computes and returns the Explanation that a particular student should receive for
    a particular question.

    INPUT (via GET params): question_id, answer_choice, user_id
    OUTPUT: explanation_id, explanation_text
    """
    if "answer_choice" not in request.GET:
        return HttpResponse("answer_choice not found in GET parameters")
    if "question_id" not in request.GET:
        return HttpResponse("question_id not found in GET parameters")
    # disabled for ease of testing
    # if 'user_id' not in request.GET:
    #     return HttpResponse('user_id not found in GET parameters')

    question = get_object_or_404(Question, id=request.GET["question_id"])
    answer_choice = int(request.GET["answer_choice"])
    # errors if more than one returned
    # answer = get_object_or_404(Answer, question=question, order=request.GET['answer_choice'])

    # still need to validate such that order is unique within answer_set, in the meantime use this
    # answer = get_list_or_404(Answer, question=question, order=answer_choice)[0]
    # also answer_choice is 1-indexed
    answer = question.answer_set.order_by("_order")[answer_choice - 1]
    mooclet = answer.mooclet_explanation

    mooclet_context = {"mooclet": mooclet}

    if "user_id" in request.GET:
        user = get_object_or_404(User, id=request.GET["user_id"])
        mooclet_context["user"] = user

    elif "user" in request.GET:
        user = get_object_or_404(User, id=request.GET["user"])
        mooclet_context["user"] = user

    version = mooclet.get_version(mooclet_context)
    explanation = version.explanation

    # update count of answers
    answer_content_type = ContentType.objects.get_for_model(Answer)
    answer_choice_count, created = Variable.objects.get_or_create(
        name="answer_choice_count",
        display_name="Count",
        content_type=answer_content_type,
    )
    value = answer_choice_count.get_data(
        {"question": question, "answer": answer}
    ).last()
    if not value:
        value = Value.objects.create(
            variable=answer_choice_count, object_id=answer.pk, value=1.0
        )
    else:
        value.value += 1.0
    value.save()

    return JsonResponse(
        {
            "explanation_id": explanation.id,
            "version_id": version.id,
            "text": explanation.text,
        }
    )


def submit_result_of_explanation(request):
    """
    # Submits a scalar score (1-7) associated with a particular student who received a
    # particular explanation.

    INPUT (via GET params): explanation_id, user_id, value (1-7)
    OUTPUT: result_id
    """
    if "explanation_id" not in request.GET:
        return HttpResponse("explanation_id not found in GET parameters")
    # if 'user_id' not in request.GET:
    #     return HttpResponse('user_id not found in GET parameters')
    if "value" not in request.GET:
        return HttpResponse("value not found in GET parameters")

    # value = (float(request.GET['value']) - 1.0) / 6.0

    result = Value(
        user=request.GET["user_id"],
        explanation=request.GET["explanation_id"],
        value=request.GET["value"],
    )
    result.save()
    return JsonResponse({"result_id": result.id})


def submit_quiz_grade(request):
    """
    Submits a quiz grade to app db

    INPUT (via GET params): user_id, quiz_id, grade
    OUTPUT: confirmation message
    """
    required_get_params = ["user_id", "quiz_id", "grade"]
    for param in required_get_params:
        if param not in request.GET:
            return JsonResponse(
                {
                    "message": "Required parameter {} not found in GET params".format(
                        param
                    )
                }
            )
    if "quizsource" in request.GET and request.GET["quizsource"] == "preview":
        # instructor preview, don't save the values
        return JsonResponse({"message": "Instructor preview, values not saved"})
    grade = float(request.GET["grade"])
    user_id = int(request.GET["user_id"])
    user = User.objects.get(pk=user_id)
    quiz_id = int(request.GET["quiz_id"])
    quiz = Quiz.objects.get(pk=quiz_id)

    Grade = Variable.objects.get(name="quiz_grade")
    value = Value(variable=Grade, user=user, object_id=quiz_id, value=grade)
    value.save()

    grade_passback(grade, user, quiz)

    return JsonResponse({"message": "Quiz grade successfully submitted"})


# TODO generic function for submitting values
def submit_value(request):
    """
    Submit a generic variable value to app db
    input: variable, value, user, [object_id, version, mooclet, quiz, course]
    output: success message
    """
    reserved_params = ["token", "user_id", "content_type", "object_id", "quizsource"]
    token = "jjw"
    if "token" not in request.GET or request.GET["token"] != token:
        return JsonResponse(
            {"message": "Required parameter token not found or incorrect"}
        )
    if "user_id" not in request.GET:
        return JsonResponse(
            {"message": "Required parameter user_id not found in GET params"}
        )

    if "quizsource" in request.GET and request.GET["quizsource"] == "preview":
        # instructor preview, don't save the values
        return JsonResponse({"message": "Instructor preview, values not saved"})

    user_id = int(request.GET["user_id"])
    user = User.objects.get(pk=user_id)
    content_type = None
    object_id = None

    if "content_type" in request.GET:
        content_type = ContentType.objects.get(model=request.GET["content_type"])
    # we may want to not allow object_id without a content_type
    if "object_id" in request.GET:
        object_id = int(request.GET["object_id"])

    count_unsaved_params = 0
    count_saved_params = 0
    for param in request.GET:
        if param not in reserved_params:
            # skip text variables since they aren't implemented
            try:
                variable_value = float(request.GET[param])

                variable, created = Variable.objects.get_or_create(
                    name=param, content_type=content_type, is_user_variable=True
                )
                value = Value(
                    variable=variable,
                    user=user,
                    object_id=object_id,
                    value=variable_value,
                )
                value.save()
                count_saved_params = count_saved_params + 1
            except ValueError:
                count_unsaved_params = count_unsaved_params + 1
                pass

    message = "{} User variables successfully submitted".format(str(count_saved_params))
    if count_unsaved_params > 0:
        message = "{} variables could not be saved".format(str(count_unsaved_params))
    return JsonResponse({"message": message})


def update_intermediates(request):
    """
    update intermediate viarables (mean, N, model params?)
    on survey completion
    inputs: token, quiz_id, question_id, version_id
    return success message
    """

    token = "jjw"
    version_content_type = ContentType.objects.get_for_model(Version)
    if "token" not in request.GET or request.GET["token"] != token:
        return JsonResponse(
            {"message": "Required parameter token not found or incorrect"}
        )

    if "quiz_id" not in request.GET:
        return JsonResponse(
            {"message": "Required parameter quiz_id not found in GET parameters"}
        )

    if "version_id" not in request.GET:
        return JsonResponse(
            {"message": "Required parameter version_id not found in GET parameters"}
        )

    if "question_id" not in request.GET:
        return JsonResponse(
            {"message": "Required parameter question_id not found in GET parameters"}
        )

    # update version level intermediate variables
    version = Version.objects.get(pk=int(request.GET["version_id"]))
    mooclet = version.mooclet
    versions = mooclet.version_set.all()
    student_ratings = (
        Variable.objects.get(name="student_rating").get_data({"version": version}).all()
    )
    rating_count = student_ratings.count()
    rating_average = student_ratings.aggregate(Avg("value"))
    rating_average = rating_average["value__avg"]
    if rating_average is None:
        rating_average = 0
    std_dev = 0
    ratings = [
        v.value
        for v in Variable.objects.filter(name="student_rating")
        .first()
        .get_data({"version": version})
        .all()
    ]
    if len(ratings) >= 1:
        std_dev = std(ratings)
    num_students_db, created = Variable.objects.get_or_create(
        name="num_students",
        display_name="Number of Students",
        content_type=version_content_type,
    )
    mean_rating_db, created = Variable.objects.get_or_create(
        name="mean_student_rating",
        display_name="Mean Student Rating",
        content_type=version_content_type,
    )
    std_dev_db, created = Variable.objects.get_or_create(
        name="rating_std_dev",
        display_name="Standard Deviation of Rating",
        content_type=version_content_type,
    )

    current_num_students = Value.objects.filter(
        variable=num_students_db, object_id=version.pk
    ).last()
    current_mean = Value.objects.filter(
        variable=mean_rating_db, object_id=version.pk
    ).last()
    current_std_dev = Value.objects.filter(
        variable=num_students_db, object_id=version.pk
    ).last()

    if current_num_students:
        current_num_students.value = float(rating_count)
        current_num_students.save()
    elif not current_num_students and rating_count:
        current_num_students = Value.objects.create(
            variable=num_students_db, object_id=version.pk, value=rating_count
        )

    if current_mean:
        current_mean.value = rating_average
        current_mean.save()
    elif not current_mean and rating_average:
        current_mean = Value.objects.create(
            variable=mean_rating_db, object_id=version.pk, value=rating_average
        )

    if current_std_dev:
        current_std_dev.value = std_dev
        current_std_dev.save()
    elif not current_std_dev and std_dev:
        current_std_dev = Value.objects.create(
            variable=std_dev_db, object_id=version.pk, value=std_dev
        )

    # simulate probabilities
    mooclet_context = {"mooclet": mooclet}
    probabilities = mooclet.simulate_probabilities(mooclet_context, iterations=10000)
    # version_counts = {version: 0 for version in versions}

    # #get versions 100 times and keep track of how often each is picked
    # num_iterations = 100
    # for i in range(1, num_iterations):
    #     version = mooclet.get_version(mooclet_context)
    #     #version = unicode(version)
    #     version_counts[version] = version_counts[version] + 1
    # versions = version_counts.keys()

    # probabilities = [float(version_counts[version]) / sum(version_counts.values()) for version in versions]
    # explanation_probability, created = Variable.objects.get_or_create(name='explanation_probability', content_type=version_content_type)
    # for version, probability in zip(versions, probabilities):
    #     explanation_probability_value = explanation_probability.get_data({'version': version}).last()
    #     if explanation_probability_value:
    #         explanation_probability_value.value = probability
    #         explanation_probability_value.save()
    #     else:
    #         #no current probability stored
    #         explanation_probability_value = Value.objects.create(variable=explanation_probability, object_id=version.pk, value=probability)

    # Question Level variables
    question = Question.objects.get(pk=int(request.GET["question_id"]))
    answers = question.answer_set.all()
    answer_content_type = ContentType.objects.get_for_model(Answer)

    answer_count = Variable.objects.get(name="answer_choice_count")
    answer_counts = {
        answer: answer_count.get_data({"question": question, "answer": answer}).last()
        for answer in answers
    }
    total_count = sum(filter(None, answer_counts.values()))
    answer_proportion, created = Variable.objects.get_or_create(
        name="answer_proportion", content_type=answer_content_type
    )
    for answer in answer_counts:
        # generate the proportion of answers
        if answer_counts[answer]:
            proportion = answer_counts[answer] / total_count
        else:  # no answer_choice_count, no one has chosen this answer
            proportion = 0.0

        value = answer_proportion.get_data(
            {"question": question, "answer": answer}
        ).last()
        if not value:
            value = Value.objects.create(
                variable=answer_proportion, object_id=answer.pk, value=proportion
            )
        else:
            value.value = proportion
        value.save()

    return JsonResponse(
        {
            "message": "Success. New variables:",
            "count": rating_count,
            "mean": rating_average,
            "standard deviation": std_dev,
            "probabilities": probabilities.values(),
        }
    )


# def submit_user_variables(request):
#      '''
#     Submits a set of user variables to app db

#     INPUT (via GET params): user_id, quiz_id, variables
#     OUTPUT: confirmation message
#     '''

#     required_get_params = ['user_id', 'quiz_id']
#     for param in required_get_params:
#         if param not in request.GET:
#             return JsonResponse({'message':'Required parameter {} not found in GET params'.format(param)})

#     user_id = int(request.GET['user_id'])
#     user = User.objects.get(pk=user_id)
#     quiz_id = int(request.GET['quiz_id'])
#     quiz = Quiz.objects.get(pk=quiz_id)

#     for param, value in request.GET:
#         if param not in required_get_params:
