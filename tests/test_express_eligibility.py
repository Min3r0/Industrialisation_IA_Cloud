"""Règle métier d'éligibilité express (ADR-0012) : chaque critère est testé isolément."""
import pytest

from express_delivery.domain.express_eligibility import EligibilityCriteria, ExpressEligibilityRule
from tests.conftest import EASY_ORDER, HARD_ORDER


@pytest.fixture
def rule() -> ExpressEligibilityRule:
    return ExpressEligibilityRule()


def test_easy_order_is_eligible(rule):
    assert rule.is_eligible(EASY_ORDER)
    assert rule.failed_criteria(EASY_ORDER) == []


def test_hard_order_is_not_eligible(rule):
    assert not rule.is_eligible(HARD_ORDER)


@pytest.mark.parametrize(("change", "criterion"), [
    ({"stock_available": 0}, "stock_indisponible"),
    ({"preparation_time_min": 36}, "preparation_trop_longue"),
    ({"hour": 18}, "commande_trop_tardive"),
    ({"weight_kg": 20.5}, "colis_trop_lourd"),
    ({"weather": "neige"}, "meteo_excluante"),
    ({"distance_km": 36}, "distance_trop_grande"),
    ({"delivery_zone": "rurale", "distance_km": 21}, "distance_trop_grande"),
])
def test_each_criterion_alone_makes_an_order_ineligible(rule, change, criterion):
    assert rule.failed_criteria({**EASY_ORDER, **change}) == [criterion]


@pytest.mark.parametrize("change", [
    {"preparation_time_min": 35},
    {"hour": 17},
    {"weight_kg": 20},
    {"weather": "orage"},
    {"distance_km": 35},
])
def test_thresholds_are_inclusive(rule, change):
    assert rule.is_eligible({**EASY_ORDER, **change})


def test_distance_limit_depends_on_the_zone(rule):
    order = {**EASY_ORDER, "distance_km": 25}
    assert rule.is_eligible({**order, "delivery_zone": "centre"})
    assert not rule.is_eligible({**order, "delivery_zone": "rurale"})


def test_unknown_zone_is_refused_instead_of_labelled(rule):
    with pytest.raises(ValueError, match="Zone de livraison inconnue"):
        rule.is_eligible({**EASY_ORDER, "delivery_zone": "suburb"})


def test_criteria_can_be_replaced_without_touching_the_rule():
    strict = ExpressEligibilityRule(EligibilityCriteria(max_preparation_min=10))
    assert not strict.is_eligible(EASY_ORDER)  # préparation de 18 min


def test_all_violated_criteria_are_reported(rule):
    assert set(rule.failed_criteria(HARD_ORDER)) == {
        "stock_indisponible", "preparation_trop_longue", "commande_trop_tardive", "distance_trop_grande",
    }
