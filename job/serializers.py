from rest_framework import serializers

from job.models import Company, Job, JobUser


class CompanyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['name']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class JobListSerializer(serializers.ModelSerializer):
    company = CompanyListSerializer()

    class Meta:
        model = Job
        fields = ['id', 'title', 'company', 'format', 'location', 'employment', 'salary', 'date_modified', 'img']


class JobSerializer(serializers.ModelSerializer):
    company = CompanySerializer()
    similar_jobs = JobListSerializer(many=True)

    class Meta:
        model = Job
        fields = "__all__"


class JobExpiredSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ["expired", "expiration_reason"]


class JobUserListSerializer(serializers.ModelSerializer):
    job = JobListSerializer()

    class Meta:
        model = JobUser
        fields = ['job', 'date_created']


class JobUserCreateSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(required=True, allow_null=False)

    class Meta:
        model = JobUser
        fields = ['job_id']
