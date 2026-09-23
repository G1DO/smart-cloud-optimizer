"""Cold-start behavior for the legacy Streamlit Home page."""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from dashboard import home


@pytest.mark.parametrize("data_days", [0, 1, 29])
def test_cold_start_progress_only_with_data(data_days, monkeypatch):
    ui = MagicMock(session_state={})
    questionnaire = MagicMock()
    monkeypatch.setattr(home, "st", ui)
    monkeypatch.setattr(home.components, "get_db_connection", MagicMock())
    monkeypatch.setattr(home.storage_db, "get_ai_recommendations", lambda *args: [])
    monkeypatch.setattr(home, "_render_questionnaire_form", questionnaire)

    home._render_cold_start("aws-TEST", data_days)

    questionnaire.assert_called_once_with("aws-TEST")
    if data_days == 0:
        ui.info.assert_not_called()
        ui.progress.assert_not_called()
    else:
        ui.progress.assert_called_once_with(data_days / 30)
        assert f"{data_days}/30" in ui.info.call_args.args[0]


@pytest.mark.parametrize("data_days, cold_start", [(29, True), (30, False)])
def test_dashboard_unlocks_at_thirty_days(data_days, cold_start, monkeypatch):
    class PageStopped(Exception):
        pass

    ui = MagicMock()
    ui.stop.side_effect = PageStopped
    render_cold_start = MagicMock()
    load_summary = MagicMock(return_value={"daily": pd.DataFrame()})
    monkeypatch.setattr(home, "st", ui)
    monkeypatch.setattr(home, "_render_cold_start", render_cold_start)
    monkeypatch.setattr(home.components, "get_current_user_id", lambda: "aws-TEST")
    monkeypatch.setattr(home.components, "get_data_days_count", lambda user_id: data_days)
    monkeypatch.setattr(home.components, "load_cost_summary", load_summary)
    for name in ("load_recommendations", "load_anomalies", "load_service_costs"):
        monkeypatch.setattr(home.components, name, MagicMock(return_value=[]))
    monkeypatch.setattr(home.components, "show_empty_state", MagicMock())

    with pytest.raises(PageStopped):
        home.render()

    if cold_start:
        render_cold_start.assert_called_once_with("aws-TEST", data_days)
        load_summary.assert_not_called()
    else:
        render_cold_start.assert_not_called()
        load_summary.assert_called_once_with("aws-TEST", days=30)
