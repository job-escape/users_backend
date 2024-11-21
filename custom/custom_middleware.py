# from django.conf import settings
# from growthbook import GrowthBook


# def growthbook_middleware(get_response):
#     def middleware(request):
#         request.gb = GrowthBook(
#             api_host="https://gb-api.jobescape.me",
#             client_key=settings.GROWTHBOOK_CLIENT_KEY,
#             # on_experiment_viewed = on_experiment_viewed
#         )
#         request.gb.load_features()

#         response = get_response(request)

#         request.gb.destroy()  # Cleanup

#         return response
#     return middleware
