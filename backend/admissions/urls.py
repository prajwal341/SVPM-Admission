from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CurrentUserView, FeeEstimateView, LoginView, LogoutView, PasswordResetCompleteView, PasswordResetStartView, RegistrationStartView, RegistrationVerifyView, ShareholderReviewViewSet, StaffDocumentDownloadView, StaffDocumentReviewView, StaffPRNLookupView, StaffStudentDocumentsView, StaffStudentRecordDetailView, StaffStudentRecordImportView, StaffStudentRecordListCreateView, StudentApplicationsView, StudentDocumentsView

router = DefaultRouter()
router.register("staff/shareholder-claims", ShareholderReviewViewSet, basename="staff-shareholder-claim")
urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/register/start/", RegistrationStartView.as_view()),
    path("auth/register/verify/", RegistrationVerifyView.as_view()),
    path("auth/password-reset/start/", PasswordResetStartView.as_view()),
    path("auth/password-reset/complete/", PasswordResetCompleteView.as_view()),
    path("me/", CurrentUserView.as_view()),
    path("staff/students/lookup/", StaffPRNLookupView.as_view()),
    path("staff/students/", StaffStudentRecordListCreateView.as_view()),
    path("staff/students/import/", StaffStudentRecordImportView.as_view()),
    path("staff/students/<int:pk>/", StaffStudentRecordDetailView.as_view()),
    path("staff/student-documents/", StaffStudentDocumentsView.as_view()),
    path("documents/", StudentDocumentsView.as_view()),
    path("applications/", StudentApplicationsView.as_view()),
    path("staff/documents/", StaffDocumentReviewView.as_view()),
    path("staff/documents/<int:document_id>/", StaffDocumentReviewView.as_view()),
    path("staff/documents/<int:document_id>/download/", StaffDocumentDownloadView.as_view()),
    path("fees/estimate/", FeeEstimateView.as_view()),
    path("", include(router.urls)),
]
