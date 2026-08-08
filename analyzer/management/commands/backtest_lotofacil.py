import json

from django.core.management.base import BaseCommand, CommandError

from analyzer.services.backtesting import run_backtest
from analyzer.services.excel_parser import parse_lotofacil_excel


class Command(BaseCommand):
    help = 'Executa backtesting walk-forward das heuristicas da Lotofacil.'

    def add_arguments(self, parser):
        parser.add_argument('file_path')
        parser.add_argument('--min-history', type=int, default=20)
        parser.add_argument('--game-count', type=int, default=3)
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **options):
        try:
            with open(options['file_path'], 'rb') as workbook:
                parse_result = parse_lotofacil_excel(workbook)
            result = run_backtest(
                parse_result.draws,
                min_history=options['min_history'],
                game_count=options['game_count'],
                seed=options['seed'],
            )
        except (OSError, ValueError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
