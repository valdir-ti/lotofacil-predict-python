from django.urls import path

from .views import (
    add_manual_game,
    confirm_ai_games_view,
    conferir_apostas,
    daily_result_create,
    daily_result_delete,
    daily_result_edit,
    daily_results,
    home,
    upload_and_predict,
)


urlpatterns = [
    path('', home, name='home'),
    path('financeiro/', daily_results, name='daily_results'),
    path('financeiro/novo/', daily_result_create, name='daily_result_create'),
    path('financeiro/<int:record_id>/editar/', daily_result_edit, name='daily_result_edit'),
    path('financeiro/<int:record_id>/excluir/', daily_result_delete, name='daily_result_delete'),
    path('financeiro/<int:record_id>/jogos/novo/', add_manual_game, name='add_manual_game'),
    path('financeiro/conferir/', conferir_apostas, name='conferir_apostas'),
    path('financeiro/confirmar-jogos/', confirm_ai_games_view, name='confirm_ai_games'),
    # Backward-compatible singular endpoint used by older clients.
    path('financeiro/confirmar-jogo/', confirm_ai_games_view, name='confirm_ai_game'),
    path('predict/upload/', upload_and_predict, name='predict_upload'),
]
