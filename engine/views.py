import csv
import json
from urllib.parse import urlencode

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, StdDev
from django.forms import ModelForm, inlineformset_factory, modelformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from ltilib.utils import display_preview
from numpy import std
from qualtrics.utils import provision_qualtrics_quiz

from .forms import *
from .models import *
from .utils import *

# from django.views import View


#### RESOURCE SELECTION ####


def quiz_create_options(request):
    return render(request, "engine/quiz_create_options.html")


def quiz_create_blank(request):
    course = None
    if request.session.get("LTI_LAUNCH"):
        course, created = Course.objects.get_or_create(
            context=request.session["LTI_LAUNCH"]["context_id"],
            name=request.session["LTI_LAUNCH"]["context_title"],
        )
        if created:
            course.save()

    quiz = Quiz(
        # user=request.user,
    )
    if course:
        quiz.course = course
    if request.user.is_authenticated():
        quiz.user = request.user
    quiz.save()

    if request.session.get("LTI_LAUNCH"):
        return redirect("lti:return_launch_url", quiz_id=quiz.id)
    else:
        context = {
            "launch_url": request.build_absolute_uri(
                reverse("lti:launch", kwargs={"quiz_id": quiz.id})
            ),
        }
        return render(request, "engine/show_launch_url.html", context)


def quiz_create_url(request):
    if request.method == "GET":
        quiz_url_form = QuizUrlForm()
        context = {"quiz_url_form": quiz_url_form}
        return render(request, "engine/quiz_create_url.html", context)
    elif request.method == "POST":
        course = None
        if request.session.get("LTI_LAUNCH"):
            course, created = Course.objects.get_or_create(
                context=request.session["LTI_LAUNCH"]["context_id"],
                name=request.session["LTI_LAUNCH"]["context_title"],
            )
        if course and created:
            course.save()
        quiz_url_form = QuizUrlForm(request.POST)
        quiz = quiz_url_form.save(commit=False)
        quiz.course = course
        if request.user.is_authenticated():
            quiz.user = request.user
        quiz.save()

        if request.session.get("LTI_LAUNCH"):
            return redirect("lti:return_launch_url", quiz_id=quiz.id)
        else:
            context = {
                "launch_url": request.build_absolute_uri(
                    reverse("lti:launch", kwargs={"quiz_id": quiz.id})
                ),
            }
            return render(request, "engine/show_launch_url.html", context)


#### UTILITY VIEWS ####


def launch_quiz(request, quiz_id):
    """
    Redirect to proper mode of displaying quiz (native or external)
    Checks if external URLs are present in quiz model fields
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    # handle redicrets to different instructor/student views here?
    # redirect to an alternate view if the quiz is complete
    # grade_data = Variable.objects.get(name='quiz_grade').get_data({'quiz':quiz,'user':request.user})
    # if grade_data:
    #     grade = grade_data.last().value
    #     if grade == 1:
    #         return redirect('quiz:complete')

    # check for external url on quiz or first question of quiz
    external_url = quiz.getExternalUrl()
    if external_url:
        extra_params = {
            # pass in django user_id as a GET parameter to survey
            "quiz_id": quiz_id,
            "user_id": request.user.id,
            "quizsource": "preview"
            if display_preview(request.user, quiz)
            else "student",
        }
        params_append_char = "&" if "?" in external_url else "?"
        return redirect(external_url + params_append_char + urlencode(extra_params))

    # otherwise use django quiz app
    else:
        if quiz.question_set.all().exists():
            question = quiz.question_set.first()
            return redirect("quiz:question", question_id=question.id)
        else:
            return redirect("quiz:placeholder")


def launch_sandbox(request):
    """
    non-lti launch that redirects user to a shared default sandbox quiz (instructor view)
    """
    quiz_id = 1
    request.session["quiz_id"] = quiz_id
    return redirect("engine:quiz_detail", quiz_id=quiz_id)


#### QUIZ MANAGEMENT ####


def launch_quiz_manager(request, quiz_id):
    """
    show the instructor view - for now, question_detail
    if the quiz has an associated questionelse quiz_detail
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if quiz.question_set.exists():
        # show question view
        question = quiz.question_set.first()
        return redirect(
            "engine:question_detail", quiz_id=quiz.pk, question_id=question.pk
        )
    else:
        return redirect("engine:quiz_detail", quiz_id=quiz.pk)


def collaborator_request(request):
    # potential researcher would have to authenticate in the course, then open this view in a new browser window/tab (outside lms)
    # display session data, researcher sends their user id to instructor
    # TODO optional instructor could create a passcode that might be required to access this view
    # show additional info to confirm session data is correct

    return render(request, "engine/collaborator_request.html")


def collaborator_create(request, quiz_id):
    # TODO could add confirmation mechanism: after entering id, user info is given to confirm the user

    course = Quiz.objects.get(pk=quiz_id).course

    if request.method == "POST":
        collaborator_form = CollaboratorForm(request.POST)
        collaborator = collaborator_form.save(commit=False)
        collaborator.course = course
        collaborator.save()

    collaborators = Collaborator.objects.filter(course=course)

    context = {"collaborator_form": CollaboratorForm(), "collaborators": collaborators}
    return render(request, "engine/collaborator_create.html", context)


def quiz_detail(request, quiz_id):
    """
    Quiz management home for instructors
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    context = {"quiz": quiz}

    return render(request, "engine/quiz_detail.html", context)


def quiz_modify(request, quiz_id):
    """
    Modify quiz info (name)
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if request.method == "GET":
        # set initial value for use_qualtrics checkbox
        use_qualtrics = True
        quiz_form = QuizForm(instance=quiz, initial={"use_qualtrics": use_qualtrics})
        context = {
            "quiz": quiz,
            "quiz_form": quiz_form,
        }

        return render(request, "engine/quiz_modify.html", context)
    elif request.method == "POST":
        quiz_form = QuizForm(request.POST)
        quiz = quiz_form.save()
        return redirect("engine:quiz_detail", quiz_id=quiz_id)


def question_detail(request, quiz_id, question_id):
    """
    question home page
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    answers = question.answer_set.all()
    context = {
        "quiz": quiz,
        "question": question,
        "answers": answers,
    }
    return render(request, "engine/question_detail.html", context)


def question_results(request, quiz_id, question_id):
    """
    Display question level results (e.g. stats about each answer)
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)

    answers = question.answer_set.all()

    # determine appropriate variables
    variables = [
        v
        for v in Variable.objects.all()
        if v.content_type and v.content_type.name == "answer"
    ]

    values_matrix = []
    # for variable in mooclet.policy.variables.all():
    for answer in answers:
        answer_values = []
        for variable in variables:
            value = variable.get_data(
                {"quiz": quiz, "question": question, "answer": answer}
            ).last()
            if value:
                answer_values.append(value.value)
            else:
                answer_values.append("n/a")
        values_matrix.append(answer_values)

    context = {
        "quiz": quiz,
        "question": question,
        "answers": answers,
        "variables": variables,
        "values_matrix": values_matrix,
    }
    return render(request, "engine/quiz_results.html", context)


def question_and_answers_modify(request, quiz_id, question_id):  #
    """
    Edit question and 4 answers all at once
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    # get existing or initialize question object
    if quiz.question_set.all().exists():
        question = quiz.question_set.first()
    else:
        question = Question()

    # handle form display
    if request.method == "GET":

        INITIAL_NUM_CHOICES = 4
        INITIAL_NUM_EXPLANATIONS = 2

        AnswerFormset = inlineformset_factory(
            Question,
            Answer,
            form=AnswerForm,
            fields=("text", "correct"),
            can_delete=False,
            extra=4,
            max_num=4,
        )

        # set initial value for use_qualtrics checkbox
        use_qualtrics = True
        if quiz.question_set.all().exists():
            use_qualtrics = bool(quiz.question_set.first().url)

        # quiz_form = QuizForm(instance=quiz,initial={'use_qualtrics':use_qualtrics})

        question_form = QuestionForm(instance=question)

        answer_formset = AnswerFormset(instance=question)

        context = {
            # 'quiz_form':CreateQuizForm(),
            # 'Question':ModelForm(Question),
            "quiz": quiz,
            "question": question,
            # 'quiz_form':quiz_form,
            "question_form": question_form,
            "answer_formset": answer_formset,
            # 'answer_formgroups':answer_formgroups,
        }

        return render(request, "engine/question_and_answers_modify.html", context)

    # handle form submission/processing
    elif request.method == "POST":

        # quiz_form = QuizForm(request.POST, instance=quiz)
        # quiz = quiz_form.save(commit=False)

        question_form = QuestionForm(request.POST, instance=question)
        question = question_form.save(commit=False)
        question.save()
        question.quiz.add(quiz)

        AnswerFormset = inlineformset_factory(
            Question,
            Answer,
            fields=("text", "correct"),
            can_delete=False,
            extra=4,
            max_num=4,
        )
        answer_formset = AnswerFormset(request.POST, instance=question)
        answers = answer_formset.save(commit=False)
        # associate mooclet instances with each answer before saving

        # TODO create separate create_mooclet page where policy can be chosen
        # for now, set to a default policy
        policy = Policy.objects.get(name="uniform_random")
        mooclet_type = MoocletType.objects.get(name="explanation")
        for answer in answers:
            if not answer.mooclet_explanation:
                mooclet = Mooclet(policy=policy, type=mooclet_type)
                mooclet.save()
                answer.mooclet_explanation = mooclet
            answer.save()

        question_form.is_valid()
        if question_form.cleaned_data["use_qualtrics"] and not question.url:
            print("starting quiz provisioning process")
            new_survey_url = provision_qualtrics_quiz(request, question)

            if not new_survey_url:
                raise Exception(
                    "quiz creation failed and did not return a qualtrics id"
                )

            question.url = new_survey_url

            # remove url field if checkbox deselected
            if not question_form.cleaned_data["use_qualtrics"] and question.url:
                question.url = ""
        question.save()

        return redirect(
            "engine:question_detail", quiz_id=quiz_id, question_id=question.pk
        )


def question_create(request, quiz_id):
    """
    Simple view for creating a new question
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    if request.method == "GET":
        question_form = QuestionForm()
        context = {
            "quiz": quiz,
            "question_form": question_form,
        }
        return render(request, "engine/question_create.html", context)
    elif request.method == "POST":
        question_form = QuestionForm(request.POST)
        question = question_form.save()
        question.quiz.add(quiz)
        question_form.is_valid()
        if question_form.cleaned_data["use_qualtrics"] and not question.url:
            print("starting quiz provisioning process")
            new_survey_url = provision_qualtrics_quiz(request, question)

            if not new_survey_url:
                raise Exception(
                    "quiz creation failed and did not return a qualtrics id"
                )

            question.url = new_survey_url

            # remove url field if checkbox deselected
            if not question_form.cleaned_data["use_qualtrics"] and question.url:
                question.url = ""
        question.save()
        return redirect("engine:quiz_detail", quiz_id=quiz.pk)


def question_modify(request, quiz_id, question_id):
    """
    Modify an existing question
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    question_form = QuestionForm(instance=question)
    context = {
        "quiz": quiz,
        "question": question,
        "question_form": question_form,
    }
    return render(request, "engine/question_modify.html", context)


def answer_list(request, quiz_id, question_id):
    """
    Answer list
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    context = {
        "quiz": quiz,
        "question": question,
    }
    return render(request, "engine/answer_list.html", context)


def answer_detail(request, quiz_id, question_id, answer_id):
    """
    Answer home page; can add explanation mooclets here
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    answer = get_object_or_404(Answer, pk=answer_id)

    context = {
        "quiz": quiz,
        "question": question,
        "answer": answer,
    }
    return render(request, "engine/answer_detail.html", context)


def answer_create(request, quiz_id, question_id):
    """
    create explanations for a single question
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)

    if request.method == "GET":
        answer_form = AnswerForm()
        context = {
            "quiz": quiz,
            "question": question,
            "answer_form": answer_form,
        }
        return render(request, "engine/answer_create.html", context)

    elif request.method == "POST":
        answer_form = AnswerForm(request.POST)
        answer = answer_form.save()
        return redirect(
            "engine:question_detail", quiz_id=quiz.pk, question_id=question.pk
        )


def answer_modify(request, quiz_id, question_id, answer_id):
    """
    modify text of answer
    """
    quiz = get_object_or_404(Answer, pk=quiz_id)
    question = get_object_or_404(Answer, pk=question_id)
    answer = get_object_or_404(Answer, pk=answer_id)
    if request.method == "GET":
        answer_form = AnswerForm(instance=answer)
        context = {
            "quiz": quiz,
            "question": question,
            "answer": answer,
            "answer_form": answer_form,
        }
        return render(request, "engine/answer_modify.html", context)

    elif request.method == "POST":
        pass


def mooclet_detail(request, **kwargs):
    """
    mooclet home page
    required kwargs: quiz, mooclet, and all parent objects
    """
    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    mooclet = get_object_or_404(Mooclet, pk=kwargs["mooclet_id"])

    # look up mooclet type and identify associated parent object

    # object class that the mooclet is attached to
    parent_content_type = mooclet.type.parent_content_type
    parent_content = ContentType.get_object_for_this_type(
        parent_content_type, pk=kwargs[parent_content_type.name + "_id"]
    )

    # populate a mooclet context dict
    mooclet_context = {}
    if parent_content_type.name == "question":
        mooclet_context["question"] = parent_content
    if parent_content_type.name == "answer":
        mooclet_context["answer"] = parent_content
        mooclet_context["question"] = parent_content.question

    versions = mooclet.version_set.all()
    version_content_type = ContentType.objects.get_for_model(Version)

    mooclet_policy_form = MoocletPolicyForm(instance=mooclet)

    # page used to display variables that are version-specific
    if request.method == "GET":

        context = {
            "quiz": quiz,
            "mooclet": mooclet,
            "versions": versions,
            "mooclet_policy_form": mooclet_policy_form,
        }

        # pass additional context variables for navigation
        context.update(mooclet_context)

        if "question" in kwargs:
            context["question"] = get_object_or_404(Question, pk=kwargs["question_id"])
        if "answer" in kwargs:
            context["answer"] = get_object_or_404(Answer, pk=kwargs["answer_id"])

        return render(request, "engine/mooclet_detail.html", context)

    elif request.method == "POST":
        # process mooclet policy form for adjusting policy
        mooclet_policy_form = MoocletPolicyForm(request.POST, instance=mooclet)
        mooclet = mooclet_policy_form.save()
        # converts dict of objs to dict of pks
        mooclet_context_pk = {
            name + "_id": obj.pk for name, obj in mooclet_context.items()
        }
        return redirect(
            "engine:mooclet_detail",
            quiz_id=quiz.pk,
            mooclet_id=mooclet.pk,
            **mooclet_context_pk
        )


def mooclet_create(request, **kwargs):
    """
    create a new mooclet
    required kwargs: quiz, type, parent object
    """

    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    mooclet_type = get_object_or_404(MoocletType, name=kwargs["type"])

    # object class that the mooclet is attached to
    parent_content_type = mooclet_type.content_type
    parent_content = ContentType.get_object_for_this_type(
        parent_content_type, pk=kwargs[parent_content_type.name + "_id"]
    )

    if request.method == "GET":

        mooclet_form = MoocletForm(initial={"type": mooclet_type})
        context = {
            "quiz": quiz,
            "mooclet_form": mooclet_form,
        }
        if "question" in kwargs:
            context["question"] = get_object_or_404(Question, pk=kwargs["question_id"])
        if "answer" in kwargs:
            context["answer"] = get_object_or_404(Answer, pk=kwargs["answer_id"])
        return render(request, "engine/mooclet_create.html", context)

    elif request.method == "POST":
        mooclet_form = MoocletForm(request.POST)
        mooclet = mooclet_form.save()
        prev_url = request.POST["prev"]
        return redirect(prev_url)


def mooclet_modify_version_values(request, **kwargs):

    mooclet_id = kwargs["mooclet_id"]
    quiz_id = kwargs["quiz_id"]

    mooclet = get_object_or_404(Mooclet, pk=mooclet_id)
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=kwargs["question_id"])
    answer = get_object_or_404(Answer, pk=kwargs["answer_id"])

    versions = mooclet.version_set.all()
    Version_ct = ContentType.objects.get_for_model(Version)
    instructor_variables = (
        mooclet.policy.variables.filter(content_type=Version_ct).order_by("pk").all()
    )

    if request.method == "GET":

        # should recieve answer_id as GET parameter, if we are navigating from an answer context
        # answer = None
        # if 'answer_id' in request.GET:
        #     answer = get_object_or_404(Answer, id=request.GET['answer_id'])

        # explanations = [version.explanation for version in mooclet.version_set.all()]

        # create m x n array of forms, where m (rows) is the number of versions and n (cols) is the number of variables
        formgroups = []
        # tablegroups = []
        for version in versions:
            forms = []
            for variable in instructor_variables:
                user = request.user if variable.is_user_variable else None
                value = Value.objects.filter(
                    object_id=version.pk, variable=variable, user=user
                ).last()

                # form for version with id = m and variable with id = n has prefix "m_n"
                prefix = "{}_{}".format(version.pk, variable.pk)
                if value:
                    form = VersionValueForm(instance=value, prefix=prefix)
                else:
                    form = VersionValueForm(prefix=prefix)
                # form = VersionValueForm(instance=value, prefix=prefix)
                forms.append(form)
            formgroups.append(forms)

        context = {
            "quiz": quiz,
            "mooclet": mooclet,
            "value_formgroups": formgroups,
            # 'value_tables':tablegroups,
            "question": question,
            "answer": answer,
            # 'user_variables':user_variables,
            "instructor_variables": instructor_variables,
            "versions": versions,
        }

        # if 'question' in kwargs:
        #     content['question'] = get_object_or_404(Question,pk=kwargs['question'])
        # if 'answer' in kwargs:
        #     content['answer'] = get_object_or_404(Answer,pk=kwargs['answer'])

        return render(request, "engine/mooclet_modify_version_values.html", context)

    elif request.method == "POST":

        for version in versions:
            for variable in instructor_variables:
                user = request.user if variable.is_user_variable else None
                value = Value.objects.filter(
                    object_id=version.pk, variable=variable, user=user
                ).last()
                if not value:
                    value = Value(object_id=version.pk, variable=variable, user=user)

                # form for version with id = m and variable with id = n has prefix "m_n"
                prefix = "{}_{}".format(version.pk, variable.pk)

                form = VersionValueForm(request.POST, instance=value, prefix=prefix)

                value = form.save(commit=False)
                value = value.save()
                # print('value for version {} and variable {} = {}'.format(version.pk,variable.pk,value.value))

        return redirect(
            "engine:mooclet_modify_version_values",
            quiz_id=quiz.pk,
            question_id=question.pk,
            answer_id=answer.pk,
            mooclet_id=mooclet.pk,
        )


def mooclet_simulate_probabilities(request, **kwargs):
    # #simulate policy and provide approximate likelihood
    mooclet = get_object_or_404(Mooclet, pk=kwargs["mooclet_id"])
    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    question = get_object_or_404(Question, pk=kwargs["question_id"])
    answer = get_object_or_404(Answer, pk=kwargs["answer_id"])
    versions = mooclet.version_set.all()
    mooclet_context = {"mooclet": mooclet}
    version_content_type = ContentType.objects.get_for_model(Version)
    # TODO indicate N
    # create a dict to count the number of times each version is picked
    version_counts = {version: 0 for version in versions}

    # get versions 100 times and keep track of how often each is picked
    num_iterations = 100
    for i in range(1, num_iterations):
        version = mooclet.get_version(mooclet_context)
        # version = unicode(version)
        version_counts[version] = version_counts[version] + 1
    versions = version_counts.keys()

    probabilities = [
        float(version_counts[version]) / sum(version_counts.values())
        for version in versions
    ]
    explanation_probability, created = Variable.objects.get_or_create(
        name="explanation_probability", content_type=version_content_type
    )
    for version, probability in zip(versions, probabilities):
        explanation_probability_value = explanation_probability.get_data(
            {"version": version}
        ).last()
        if explanation_probability_value:
            explanation_probability_value.value = probability
            explanation_probability_value.save()
        else:
            # no current probability stored
            explanation_probability_value = Value.objects.create(
                variable=explanation_probability,
                object_id=version.pk,
                value=probability,
            )
    probabilities = [
        "{:.2f}%".format(probability * 100) for probability in probabilities
    ]
    versions = [unicode(version) for version in versions]
    context = {
        "quiz": quiz,
        "mooclet": mooclet,
        "question": question,
        "answer": answer,
        "num_iterations": num_iterations,
        "version_probabilities": zip(versions, probabilities),
    }
    return render(request, "engine/mooclet_simulate_probabilities.html", context)


def mooclet_list_values(request, **kwargs):
    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    mooclet = get_object_or_404(Mooclet, pk=kwargs["mooclet_id"])
    question = get_object_or_404(Question, pk=kwargs["question_id"])
    answer = get_object_or_404(Answer, pk=kwargs["answer_id"])
    values = []
    # for variable in mooclet.policy.variables.all():
    for variable in Variable.objects.all():
        for value in variable.get_data(
            {"quiz": quiz, "question": question, "answer": answer, "mooclet": mooclet}
        ):
            values.append(value)

    context = {
        "quiz": quiz,
        "mooclet": mooclet,
        "question": question,
        "answer": answer,
        "values": values,
    }
    return render(request, "engine/mooclet_list_values.html", context)


def mooclet_results(request, **kwargs):
    mooclet = get_object_or_404(Mooclet, pk=kwargs["mooclet_id"])
    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    question = get_object_or_404(Question, pk=kwargs["question_id"])
    answer = get_object_or_404(Answer, pk=kwargs["answer_id"])
    version_content_type = ContentType.objects.get_for_model(Version)

    # determine appropriate variables
    variables = []
    variables.append(
        Variable.objects.get_or_create(
            name="explanation_probability", content_type=version_content_type
        )[0]
    )
    variables.append(
        Variable.objects.get_or_create(
            name="mean_student_rating",
            display_name="Mean Student Rating",
            content_type=version_content_type,
        )[0]
    )
    variables.append(
        Variable.objects.get_or_create(
            name="num_students",
            display_name="Number of Students",
            content_type=version_content_type,
        )[0]
    )
    variables.append(
        Variable.objects.get_or_create(
            name="rating_std_dev",
            display_name="Standard Deviation of Rating",
            content_type=version_content_type,
        )[0]
    )
    # variables = [v for v in Variable.objects.all() if v.content_type.name == 'version']
    versions = mooclet.version_set.all()
    values_matrix = []
    # for variable in mooclet.policy.variables.all():
    for version in versions:
        version_values = []
        for variable in variables:
            new_value = None
            # value = variable.get_data({'quiz':quiz, 'version':version }).last()

            if variable.name == "mean_student_rating":
                new_value = (
                    Variable.objects.filter(name="student_rating")
                    .first()
                    .get_data({"quiz": quiz, "version": version})
                    .all()
                    .aggregate(Avg("value"))
                )
                new_value = new_value["value__avg"]
            elif variable.name == "num_students":
                new_value = (
                    Variable.objects.filter(name="student_rating")
                    .first()
                    .get_data({"quiz": quiz, "version": version})
                    .count()
                )
            elif variable.name == "rating_std_dev":

                ratings = [
                    v.value
                    for v in Variable.objects.filter(name="student_rating")
                    .first()
                    .get_data({"quiz": quiz, "version": version})
                    .all()
                ]
                if len(ratings) >= 1:
                    new_value = std(ratings)
                # new_value = new_value['value__stddev']
            #     new_value = Variable.objects.get(name='student_rating').get_data({'quiz':quiz, 'version':version }).count()
            # new_value = Variable.objects.filter(name='student_rating').first().get_data({'quiz':quiz, 'version':version }).all().aggregate(StdDev('value', sample=True))
            value = Value.objects.filter(variable=variable, object_id=version.pk).last()

            if new_value and value:
                value.value = new_value
                value.save()
                version_values.append("{:.2f}".format(value.value))
            elif new_value and not value:
                value = Value.objects.create(
                    variable=variable, object_id=version.pk, value=new_value
                )
                version_values.append("{:.2f}".format(value.value))
            elif value and not new_value:
                version_values.append("{:.2f}".format(value.value))
            else:
                version_values.append("n/a")
        values_matrix.append(version_values)

    context = {
        "quiz": quiz,
        "mooclet": mooclet,
        "question": question,
        "answer": answer,
        "versions": versions,
        "variables": variables,
        "values_matrix": values_matrix,
    }
    return render(request, "engine/mooclet_results.html", context)


def version_modify(request, **kwargs):
    """
    modify version, by redirecting to correct version object's modify view
    """
    quiz = get_object_or_404(Answer, pk=kwargs["quiz_id"])
    version = get_object_or_404(Version, pk=kwargs["version_id"])
    mooclet = version.mooclet

    # send to apppropriate interface, based on what the version model of the mooclet
    if mooclet.type.name == "explanation":
        question = get_object_or_404(Question, pk=kwargs["question_id"])
        answer = get_object_or_404(Answer, pk=kwargs["answer_id"])
        return redirect(
            "engine:explanation_modify",
            quiz_id=quiz.pk,
            question_id=question.pk,
            answer_id=answer.pk,
            mooclet_id=mooclet.pk,
            version_id=version.pk,
        )
    else:
        return HttpResponse("Not implemented")


def version_create(request, **kwargs):
    quiz = get_object_or_404(Answer, pk=kwargs["quiz_id"])
    mooclet = get_object_or_404(Mooclet, pk=kwargs["mooclet_id"])

    # send to apppropriate interface, based on what the version model of the mooclet
    if mooclet.type.name == "explanation":
        question = get_object_or_404(Question, pk=kwargs["question_id"])
        answer = get_object_or_404(Answer, pk=kwargs["answer_id"])
        return redirect(
            "engine:explanation_create",
            quiz_id=quiz.pk,
            question_id=question.pk,
            answer_id=answer.pk,
            mooclet_id=mooclet.pk,
        )
    else:
        return HttpResponse("Not implemented")


def explanation_list(request, quiz_id, question_id):
    """
    list explanations for a single question (multiple choices)
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = quiz.question_set.first()
    answers = question.answer_set.order_by("_order")
    context = {
        "quiz": quiz,
        "question": question,
        "answers": answers,
    }

    return render(request, "engine/explanation_list.html", context)


def explanation_create(request, quiz_id, question_id, answer_id, mooclet_id):
    """
    create new explanation version
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    answer = get_object_or_404(Answer, pk=answer_id)
    mooclet = get_object_or_404(Mooclet, pk=mooclet_id)

    if request.method == "GET":
        context = {
            "explanation_form": ExplanationForm(),
            "quiz": quiz,
            "question": question,
            "answer": answer,
            "mooclet": mooclet,
        }
        return render(request, "engine/explanation_create.html", context)

    elif request.method == "POST":
        explanation_form = ExplanationForm(request.POST)
        explanation = explanation_form.save(commit=False)
        explanation.mooclet = mooclet
        explanation.save()

        return redirect(
            "engine:mooclet_detail",
            quiz_id=quiz_id,
            question_id=question_id,
            answer_id=answer_id,
            mooclet_id=mooclet_id,
        )


def explanation_modify(
    request, quiz_id, question_id, answer_id, mooclet_id, version_id
):
    """
    modify an explanation version
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    answer = get_object_or_404(Answer, pk=answer_id)
    mooclet = get_object_or_404(Mooclet, pk=mooclet_id)
    version = get_object_or_404(Version, pk=version_id)
    explanation = version.explanation

    if request.method == "GET":
        context = {
            "quiz": quiz,
            "question": question,
            "answer": answer,
            "mooclet": mooclet,
            "version": version,
            "explanation": explanation,
            "explanation_form": ExplanationModifyForm(instance=explanation),
        }
        return render(request, "engine/explanation_modify.html", context)

    elif request.method == "POST":
        explanation_form = ExplanationModifyForm(request.POST, instance=explanation)
        explanation_form.is_valid()
        if explanation_form.cleaned_data["delete"]:
            explanation = explanation.delete()
        else:
            explanation = explanation_form.save()

        return redirect(
            "engine:mooclet_detail",
            quiz_id=quiz_id,
            question_id=question_id,
            answer_id=answer_id,
            mooclet_id=mooclet_id,
        )


def tool_instructions(request, quiz_id, question_id):
    """
    instructions for using the tool. Quiz and Question needed for navigation
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    question = get_object_or_404(Question, pk=question_id)
    context = {
        "quiz": quiz,
        "question": question,
    }
    return render(request, "engine/instructions.html", context)


def get_question_results(request, **kwargs):
    quiz = get_object_or_404(Quiz, pk=kwargs["quiz_id"])
    question = get_object_or_404(Question, pk=kwargs["question_id"])
    answers = question.answer_set.all()
    mooclets = answers.values_list("mooclet_explanation", flat=True)
    mooclets = Mooclet.objects.filter(id__in=mooclets)
    versions = Version.objects.filter(
        mooclet__in=mooclets
    ).all()  # [mooclet.version_set.all() for mooclet in mooclets]
    values = []

    # for variable in Variable.objects.all():
    #     for value in variable.get_data({'quiz':quiz, 'question':question, 'answer':answer, 'mooclet':mooclet}):
    #         values.append(value)

    try:
        calculus_condition = Variable.objects.get(name="calculus_condition")
    except Variable.DoesNotExist:
        calculus_condition = None

    Grade = Variable.objects.get(name="quiz_grade")
    grades = Grade.get_data(context={"quiz": quiz})

    users = grades.values_list("user", flat=True)
    rating = Variable.objects.get(name="student_rating")
    user_ratings = Value.objects.filter(
        variable=rating,
        object_id__in=[version.pk for version in versions],
        user__in=users,
    ).all()

    results = []
    for user in users:
        user_result = []
        user_result.append(user)
        user_result.append(quiz.pk)
        user_result.append(quiz.name)

        user_rating = user_ratings.filter(user=user).first()
        if user_rating:

            version = versions.get(pk=user_rating.object_id)

            answer = version.mooclet.answer_set.first()

            answer_chosen = answer.pk

            answer_chosen_value = answer.text

            version_pk = version.pk
            version_text = version
            user_rating_value = user_rating.value
            user_rating_time = user_rating.timestamp

        else:
            version = ""

            answer = ""

            answer_chosen = ""

            answer_chosen_value = ""

            version_pk = ""
            version_text = ""
            user_rating_value = ""
            user_rating_time = ""

        if calculus_condition and user_rating:
            condition = calculus_condition.get_data({"version": version}).first()
            if condition:
                condition = condition.value

        else:
            condition = ""

        user_result.append(answer_chosen)
        user_result.append(answer_chosen_value)

        user_result.append(condition)

        user_result.append(version_pk)
        user_result.append(version_text)

        user_result.append(user_rating_value)
        user_result.append(user_rating_time)
        user_grade = grades.filter(user=user).first()
        user_result.append(user_grade.value)
        user_result.append(user_grade.timestamp)

        results.append(user_result)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="results.csv"'

    # TODO: add 'canvas_lti_user_id'
    headers = (
        "user_id",
        "quiz_id",
        "quiz_name",
        "answer_chosen",
        "answer_chosen_value",
        "condition",
        "mooclet_version_id",
        "mooclet_version_text",
        "user_rating",
        "user_rating_time",
        "user_grade",
        "user_grade_time",
    )

    writer = csv.writer(response)

    writer.writerow(headers)
    for result in results:
        writer.writerow(result)

    return response


def question_comparison(request, **kwargs):
    # request contains a version id and a quiz_id
    version = Version.objects.get(pk=request.GET["version_id"])

    # get the rating variable and get all student ratings
    rating = Variable.objects.get(name="student_rating")
    rating_data = rating.get_data(context={"version": version})

    # get each user who provided a rating
    users = rating_data.values("user")

    print(users)

    grade = Variable.objects.get(name="quiz_grade")
    # get the grades for the users who saw version = version_id on the new subsequent problem
    grade_data = Value.objects.filter(
        variable=grade, object_id=request.GET["quiz_id"], user__in=users
    )

    grade_count = grade_data.count()
    grade_average = grade_data.aggregate(Avg("value"))
    grade_average = grade_average["value__avg"]
    return JsonResponse({"grade count": grade_count, "average": grade_average})


def calculus_comparison(request, **kwargs):
    """
    Get ratings and grades for short versus link conditions of all
    week 3 problems in calculus. split them by correct versus incorrect.
    Where grade is defined as:
    if problem = week3q1
    grade = average(week3q2grade, week3q3 grade)
    else if problem = week3q2
    grade = week3q3grade
    else if problem=week3q3
    do nothing

    arguments: start_problem, [list of following problems] in next_problems=2,3,4,5

    """
    condition = Variable.objects.get(name="condition")
    grade = Variable.objects.get(name="quiz_grade")

    week3q1quiz = Quiz.objects.get(pk=request.GET["start_problem"])  # quiz id
    week3q2quiz = Quiz.objects.get(pk=2)  # quiz id
    week3q3quiz = Quiz.objects.get(pk=3)  # quiz id
    week3quizzes = [week3q1quiz, week3q2quiz, week3q3quiz]

    answers = {}
    ratings_short_correct = 0
    ratings_short_incorrect = 0
    rating_link_correct = 0
    rating_link_incorrect = 0

    grade_short_correct = 0
    grade_short_incorrect = 0
    grade_link_correct = 0
    grade_link_incorrect = 0

    # collect the answers intoa dict of {quiz: [answer1,answer2,answer3...]}
    for quiz in week3quizzes:
        answers[quiz] = quiz.question_set.first().answer_set.all()
        # get mooclets
        for answer in answers[quiz]:
            mooclet = answer.mooclet_explanation
            # get the versions
            versions = Version.objects.filter(mooclet=mooclet).all()
            for version in versions:
                version_condition = condition.get_data(
                    {"version": version}
                ).first()  # 1 = short, 2 = long
                ratings = (
                    Variable.objects.filter(name="student_rating")
                    .first()
                    .get_data({"quiz": quiz, "version": version})
                    .all()
                )
                rating_avg = ratings.aggregate(Avg("value"))
                rating_avg = rating_avg["value__avg"]

                users = ratings.values("user")

                if quiz == week3q1quiz:
                    # grade = avg(week3q2quizgrade, week3q3grade)
                    week3q2q3grade = Value.objects.filter(
                        variable=grade,
                        user__in=users,
                        object_id__in=[week3q2quiz.pk, week3q3quiz.pk],
                    ).all()
                    grade_average = week3q2q3grade.aggregate(Avg("value"))
                    grade_average = grade_average["value__avg"]

                elif quiz == week3q2quiz:
                    week3grade = Value.objects.filter(
                        variable=grade, user__in=users, object_id=week3q3quiz.pk
                    ).all()
                    grade_average = week3grade.aggregate(Avg("value"))
                    grade_average = grade_average["value__avg"]

                if (
                    answer.correct
                    and version_condition
                    and version_condition.value == 1
                ):  # short
                    if grade_average:
                        if grade_short_correct == 0:
                            grade_short_correct = grade_average
                        else:
                            grade_short_correct = mean(
                                grade_short_correct, grade_average
                            )

                elif (
                    answer.correct
                    and version_condition
                    and version_condition.value == 2
                ):  # long
                    if grade_average:
                        if grade_link_correct == 0:
                            grade_link_correct = grade_average
                        else:
                            grade_link_correct = mean(grade_link_correct, grade_average)

                elif (
                    not answer.correct
                    and version_condition
                    and version_condition.value == 1
                ):
                    if grade_average:
                        if grade_short_incorrect == 0:
                            grade_short_incorrect = grade_average
                        else:
                            grade_short_incorrect = mean(
                                ratings_short_incorrect, grade_average
                            )

                elif (
                    not answer.correct
                    and version_condition
                    and version_condition.value == 2
                ):
                    if grade_average:
                        if grade_link_incorrect == 0:
                            grade_link_incorrect = grade_average
                        else:
                            grade_link_incorrect = mean(
                                grade_link_incorrect, grade_average
                            )

    return JsonResponse(
        {
            "rating_short_correct": ratings_short_correct,
            "rating_short_incorrect": ratings_short_incorrect,
            "rating_link_correct": rating_link_correct,
            "rating_link_incorrect": rating_link_incorrect,
            "grade_short_correct": grade_short_correct,
            "grade_short_incorrect": grade_short_incorrect,
            "grade_link_correct": grade_link_correct,
            "grade_link_incorrect": grade_link_incorrect,
        }
    )
