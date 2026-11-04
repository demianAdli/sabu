"""
Sabu project
jug_sim_buildings package
eligibility_rules module
Evaluate scenario preparation policies and preserve rejection reasons.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import math

from marshmallow import ValidationError, fields


ELIGIBILITY_RULES = (
    {'field': 'name', 'check': 'nonblank',
     'reason': 'Required string is blank (scenario rule).'},
    {'field': 'address', 'check': 'nonblank',
     'reason': 'Required string is blank (scenario rule).'},
    {'field': 'function', 'check': 'nonblank',
     'reason': 'Required string is blank (scenario rule).'},
    {'field': 'height', 'check': 'minimum', 'minimum': 0, 'inclusive': False,
     'reason': 'Height must be finite and positive (scenario rule).'},
    {'field': 'year_of_construction', 'check': 'minimum', 'minimum': 0, 'inclusive': False,
     'reason': 'Year must be a positive exact integer (scenario rule).'},
    {'field': 'citygisoo_area', 'check': 'minimum', 'minimum': 25, 'inclusive': True,
     'coerce_numeric': True,
     'unit': 'm2',
     'reason': 'citygisoo_area is below the minimum of 25 m2 (scenario rule).'},
    {'field': 'function', 'check': 'disallowed_values', 'values': ('6911', '2699'),
     'reason': 'Insufficient LCA data for building function {value}.'},
)


def _rejection(field, reason, value):
    return {'field': f'properties.{field}', 'reason': reason, 'value': deepcopy(value)}


def check_nonblank(properties, field, reason):
    """Check an already normalized required string property."""
    value = properties.get(field)
    if not isinstance(value, str) or not value.strip():
        return _rejection(field, reason, value)
    return None


def check_minimum(properties, field, minimum, reason, *, inclusive=True, coerce_numeric=False):
    """Check normalized numbers, optionally parsing a raw property without rewriting it."""
    value = properties.get(field)
    try:
        if field not in properties:
            raise ValueError(f'{field} is missing.')
        if value is None:
            raise ValueError(f'{field} is null.')
        if isinstance(value, bool):
            raise ValueError(f'Boolean is not a {field}.')
        number = fields.Float(required=True).deserialize(value) if coerce_numeric else value
        if type(number) not in (int, float):
            raise ValueError(f'{field} must be numeric.')
        # Normalized integers must not be rounded or overflow through a float conversion.
        if type(number) is float and not math.isfinite(number):
            raise ValueError(f'{field} must be finite.')
        if number < minimum or (not inclusive and number == minimum):
            raise ValueError(reason)
    except (ValidationError, ValueError, TypeError, OverflowError) as exc:
        return _rejection(field, str(exc), value)
    return None


def check_disallowed_values(properties, field, values, reason):
    """Match normalized property values and explain a configured exclusion."""
    value = properties.get(field)
    if value in values:
        return _rejection(field, reason.format(field=field, value=value), value)
    return None


def evaluate_eligibility(properties, *, original_properties=None, invalid_fields=()):
    """Collect policy errors, skipping fields that already failed normalization."""
    errors = []
    invalid_fields = set(invalid_fields)
    for rule in ELIGIBILITY_RULES:
        field = rule['field']
        if field in invalid_fields:
            continue
        if rule['check'] == 'nonblank':
            error = check_nonblank(properties, field, rule['reason'])
        elif rule['check'] == 'minimum':
            error = check_minimum(properties, field, rule['minimum'], rule['reason'],
                                  inclusive=rule['inclusive'],
                                  coerce_numeric=rule.get('coerce_numeric', False))
        elif rule['check'] == 'disallowed_values':
            error = check_disallowed_values(properties, field, rule['values'], rule['reason'])
        else:
            raise ValueError(f"Unknown eligibility check: {rule['check']}")
        if error is not None:
            if original_properties is not None:
                error['value'] = deepcopy(original_properties.get(field))
            errors.append(error)
            invalid_fields.add(field)
    return errors


def eligibility_rule_descriptions():
    """Describe the configured policies for preparation metadata."""
    descriptions = []
    for rule in ELIGIBILITY_RULES:
        field = rule['field']
        if rule['check'] == 'nonblank':
            descriptions.append(f'{field} must be a nonblank string.')
        elif rule['check'] == 'minimum':
            comparison = 'at least' if rule['inclusive'] else 'greater than'
            unit = f" {rule['unit']}" if rule.get('unit') else ''
            descriptions.append(f"{field} must be present, numeric, finite, and {comparison} "
                                f"{rule['minimum']}{unit}.")
        elif rule['check'] == 'disallowed_values':
            values = ', '.join(str(value) for value in rule['values'])
            reason = rule['reason'].format(field=field, value=' or '.join(map(str, rule['values'])))
            descriptions.append(f'{field} must not be any of: {values}. {reason}')
        else:
            raise ValueError(f"Unknown eligibility check: {rule['check']}")
    return descriptions
