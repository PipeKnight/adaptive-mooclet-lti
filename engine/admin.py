from django.contrib import admin

# Register your models here.
from .models import *

class QuizAdmin (admin.ModelAdmin):
	list_display = ['id','name','user']

class QuestionAdmin (admin.ModelAdmin):
	list_display = ['id','get_quiz_id','quiz','text']

	def get_quiz_id(self,obj):
		return obj.quiz.id

class AnswerAdmin (admin.ModelAdmin):
	list_display = ['id','question','text','correct','mooclet']

# class ExplanationAdmin (admin.ModelAdmin):
# 	list_display = ['id','answer','text']

class ResultAdmin (admin.ModelAdmin):
	list_display = ['id','user','explanation','value']

class MoocletAdmin (admin.ModelAdmin):
	list_display = ['id','version_type','policy']

class VersionAdmin(admin.ModelAdmin):
	list_display = ['id','mooclet']

class PolicyAdmin(admin.ModelAdmin):
	filter_horizontal = ('variables',)

admin.site.register(Quiz, QuizAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Answer, AnswerAdmin)
admin.site.register(Explanation)
admin.site.register(Mooclet,MoocletAdmin)
admin.site.register(Version,VersionAdmin)
admin.site.register(Variable)
admin.site.register(Value)
admin.site.register(Policy, PolicyAdmin)
admin.site.register(MoocletType)




# admin.site.register(Outcome)