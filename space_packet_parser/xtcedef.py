"""Module for parsing XTCE xml files to specify packet format"""
# Standard
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from dataclasses import dataclass, field
import inspect
import logging
import struct
from typing import Tuple, Union, Optional, Protocol, Any, List, TextIO, Dict
import warnings
# Installed
import lxml.etree as ElementTree

logger = logging.getLogger(__name__)


# Exceptions
class ElementNotFoundError(Exception):
    """Exception for missing XML element"""
    pass


class ComparisonError(Exception):
    """Exception for problems performing comparisons"""
    pass


class FormatStringError(Exception):
    """Error indicating a problem determining how to parse a variable length string."""
    pass


class DynamicLengthBinaryParameterError(Exception):
    """Exception to raise when we try to parse a dynamic length binary field as fixed length"""
    pass


class CalibrationError(Exception):
    """For errors encountered during value calibration"""
    pass


class InvalidParameterTypeError(Exception):
    """Error raised when someone is using an invalid ParameterType element"""
    pass


# Common comparable mixin
class AttrComparable(metaclass=ABCMeta):
    """Generic class that provides a notion of equality based on all non-callable, non-dunder attributes"""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError(f"No method to compare {type(other)} with {self.__class__}")

        compare = inspect.getmembers(self, lambda a: not inspect.isroutine(a))
        compare = [attr[0] for attr in compare
                   if not (attr[0].startswith('__') or attr[0].startswith(f'_{self.__class__.__name__}__'))]
        for attr in compare:
            if getattr(self, attr) != getattr(other, attr):
                print(f'Mismatch was in {attr}. {getattr(self, attr)} != {getattr(other, attr)}')
                return False
        return True


@dataclass
class ParsedDataItem:
    """Representation of a parsed parameter

    Parameters
    ----------
    name : str
        Parameter name
    unit : str
        Parameter units
    raw_value : any
        Raw representation of the parsed value. May be lots of different types but most often an integer
    derived_value : float or str
        May be a calibrated value or an enum lookup
    short_description : str
        Parameter short description
    long_description : str
        Parameter long description
    """
    name: str
    raw_value: Union[bytes, float, int, str]
    unit: Optional[str] = None
    derived_value: Optional[Union[float, str]] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None


# Matching logical objects
class MatchCriteria(AttrComparable, metaclass=ABCMeta):
    """<xtce:MatchCriteriaType>
    This class stores criteria for performing logical operations based on parameter values
    Classes that inherit from this ABC include those that represent <xtce:Comparison>, <xtce:ComparisonList>,
    <xtce:BooleanExpression> (not supported), and <xtce:CustomAlgorithm> (not supported)
    """

    # Valid operator representations in XML. Note: the XTCE spec only allows for &gt; style representations of < and >
    #   Python's XML parser doesn't appear to support &eq; &ne; &le; or &ge;
    # We have implemented support for bash-style comparisons just in case.
    _valid_operators = {
        "==": "__eq__", "eq": "__eq__",  # equal to
        "!=": "__ne__", "neq": "__ne__",  # not equal to
        "&lt;": "__lt__", "lt": "__lt__", "<": "__lt__",  # less than
        "&gt;": "__gt__", "gt": "__gt__", ">": "__gt__",  # greater than
        "&lt;=": "__le__", "leq": "__le__", "<=": "__le__",  # less than or equal to
        "&gt;=": "__ge__", "geq": "__ge__", ">=": "__ge__",  # greater than or equal to
    }

    @classmethod
    @abstractmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Abstract classmethod to create a match criteria object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        raise NotImplementedError()

    @abstractmethod
    def evaluate(self, parsed_data: dict, current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : any, Optional
            Uncalibrated value that is currently being matched (e.g. as a candidate for calibration).
            Used to resolve comparisons that reference their own raw value as a condition.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """
        raise NotImplementedError()


class Comparison(MatchCriteria):
    """<xtce:Comparison>"""

    def __init__(self, required_value: any, referenced_parameter: str,
                 operator: str = "==", use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        operator : str
            String representation of the comparison operation. e.g. "<=" or "leq"
        required_value : any
            Value with which to compare the referenced parameter using the operator. This value is dynamically
            coerced to the referenced parameter type during evaluation.
        referenced_parameter : str
            Name of the parameter to compare with the value.
        use_calibrated_value : bool
            Whether or not to calibrate the value before performing the comparison.
        """
        self.required_value = required_value
        self.referenced_parameter = referenced_parameter
        self.operator = operator
        self.use_calibrated_value = use_calibrated_value
        self._validate()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.referenced_parameter}{self.operator}{self.required_value}>"

    def _validate(self):
        """Validate state as logically consistent.

        Returns
        -------
        None
        """
        if self.operator not in self._valid_operators:
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(self._valid_operators.keys())}")

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'Comparison':
        """Create

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : Comparison
        """
        use_calibrated_value = True  # Default
        if 'useCalibratedValue' in element.attrib:
            use_calibrated_value = element.attrib['useCalibratedValue'].lower() == 'true'

        value = element.attrib['value']

        parameter_name = element.attrib['parameterRef']
        operator = '=='
        if 'comparisonOperator' in element.attrib:
            operator = element.attrib['comparisonOperator']

        return cls(value, parameter_name, operator=operator, use_calibrated_value=use_calibrated_value)

    def evaluate(self, parsed_data: dict, current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate comparison down to a boolean. If the parameter to compare is not present in the parsed_data dict,
        we assume that we are comparing against the current raw value in current_parsed_value.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : Union[int, float]
            Optional. Uncalibrated value that is currently a candidate for calibration and so has not yet been added
            to the parsed_data dict. Used to resolve calibrator conditions that reference their own
            raw value as a comparate.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """
        if self.referenced_parameter in parsed_data:
            if self.use_calibrated_value:
                parsed_value = parsed_data[self.referenced_parameter].derived_value
                if not parsed_value:
                    raise ComparisonError(f"Comparison {self} was instructed to useCalibratedValue (the default)"
                                          f"but {self.referenced_parameter} does not appear to have a derived value.")
            else:
                parsed_value = parsed_data[self.referenced_parameter].raw_value
        elif current_parsed_value is not None:
            # Assume then that the comparison is a reference to its own uncalibrated value
            parsed_value = current_parsed_value
            if self.use_calibrated_value:
                warnings.warn("Performing a comparison against a current value (e.g. a Comparison within a "
                              "context calibrator contains a reference to its own uncalibrated value but use_"
                              "calibrated_value is set to true. This is nonsensical. Using the uncalibrated value...")
        else:
            raise ValueError("Attempting to resolve a Comparison expression but the referenced parameter does not "
                             "appear in the parsed data so far and no current raw value was passed "
                             "to compare with.")

        operator = self._valid_operators[self.operator]
        t_comparate = type(parsed_value)
        try:
            required_value = t_comparate(self.required_value)
        except ValueError as err:
            raise ComparisonError(f"Unable to coerce {self.required_value} of type {type(self.required_value)} to "
                                  f"type {t_comparate} for comparison evaluation.") from err
        if required_value is None or parsed_value is None:
            raise ValueError(f"Error in Comparison. Cannot compare {required_value} with {parsed_value}. "
                             "Neither should be None.")

        # x.__le__(y) style call
        return getattr(parsed_value, operator)(required_value)


class Condition(MatchCriteria):
    """<xtce:Condition>
    Note: This xtce model doesn't actually inherit from MatchCriteria in the UML model
    but it's functionally close enough that we inherit the class here.
    """

    def __init__(self,
                 left_param: str,
                 operator: str,
                 right_param: Optional[str] = None,
                 right_value: Optional[Any] = None,
                 left_use_calibrated_value: bool = True,
                 right_use_calibrated_value: bool = True):
        """Constructor

        Parameters
        ----------
        left_param : str
            Parameter name on the LH side of the comparison
        operator : str
            Member of MatchCriteria._valid_operators.
        right_param : Optional[str]
            Parameter name on the RH side of the comparison.
        right_value: Optional[Any]
            Used in case of comparison with a fixed xtce:Value on the RH side.
        left_use_calibrated_value : bool, Optional
            Default is True. If False, comparison is made against the uncalibrated value.
        right_use_calibrated_value: bool, Optional
            Default is True. If False, comparison is made against the uncalibrated value.
        """
        self.left_param = left_param
        self.right_param = right_param
        self.right_value = right_value
        self.operator = operator
        self.right_use_calibrated_value = right_use_calibrated_value
        self.left_use_calibrated_value = left_use_calibrated_value
        self._validate()

    def _validate(self):
        """Check that the instantiated object actually makes logical sense.

        Returns
        -------
        None
        """
        if self.operator not in self._valid_operators:
            raise ValueError(f"Unrecognized operator syntax {self.operator}. "
                             f"Must be one of "
                             f"{set(self._valid_operators.keys())}")
        if self.right_param and self.right_value:
            raise ComparisonError(f"Received both a right_value and a right_param reference to Condition {self}.")
        if self.right_value and self.right_use_calibrated_value:
            raise ComparisonError(f"Unable to use calibrated form of a fixed value in Condition {self}.")

    @staticmethod
    def _parse_parameter_instance_ref(element: ElementTree.Element):
        """Parse an xtce:ParameterInstanceRef element

        Parameters
        ----------
        element: ElementTree.Element
            xtce:ParameterInstanceRef element

        Returns
        -------
        parameter_name: str
            Name of referenced parameter
        use_calibrated_value: bool
            Whether to use the calibrated form of the referenced parameter
        """
        parameter_name = element.attrib['parameterRef']
        use_calibrated_value = True  # Default
        if 'useCalibratedValue' in element.attrib:
            use_calibrated_value = element.attrib['useCalibratedValue'].lower() == 'true'
        return parameter_name, use_calibrated_value

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Classmethod to create a Condition object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        operator = element.find('xtce:ComparisonOperator', ns).text
        params = element.findall('xtce:ParameterInstanceRef', ns)
        if len(params) == 1:
            left_param, use_calibrated_value = cls._parse_parameter_instance_ref(params[0])
            right_value = element.find('xtce:Value', ns).text
            return cls(left_param, operator, right_value=right_value,
                       left_use_calibrated_value=use_calibrated_value,
                       right_use_calibrated_value=False)
        if len(params) == 2:
            left_param, left_use_calibrated_value = cls._parse_parameter_instance_ref(params[0])
            right_param, right_use_calibrated_value = cls._parse_parameter_instance_ref(params[1])
            return cls(left_param, operator, right_param=right_param,
                       left_use_calibrated_value=left_use_calibrated_value,
                       right_use_calibrated_value=right_use_calibrated_value)
        raise ValueError(f'Failed to parse a Condition element {element}. '
                         'See 3.4.3.4.2 of XTCE Green Book CCSDS 660.1-G-2')

    def evaluate(self, parsed_data: dict, current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate match criteria down to a boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : Optional[Union[int, float]]
            Current value being parsed. NOTE: This is currently ignored. See the TODO item below.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """

        def _get_parsed_value(parameter_name: str, use_calibrated: bool):
            """Retrieves the previously parsed value from the passed in parsed_data"""
            try:
                return parsed_data[parameter_name].derived_value if use_calibrated \
                    else parsed_data[parameter_name].raw_value
            except KeyError as e:
                raise ComparisonError(f"Attempting to perform a Condition evaluation on {self.left_param} but "
                                      "the referenced parameter does not appear in the hitherto parsed data passed to "
                                      "the evaluate method. If you intended a comparison against the raw value of the "
                                      "parameter currently being parsed, unfortunately that is not currently supported."
                                      ) from e

        # TODO: Consider allowing one of the parameters to be the parameter currently being evaluated.
        #    This isn't explicitly provided for in the XTCE spec but it seems reasonable to be able to
        #    perform conditionals against the current raw value of a parameter, e.g. while determining if it
        #    should be calibrated. Note that only one of the parameters can be used this way and it must reference
        #    an uncalibrated value so the logic and error handling must be done carefully.
        left_value = _get_parsed_value(self.left_param, self.left_use_calibrated_value)
        # Convert XML operator representation to a python-compatible operator (e.g. '&gt;' to '__gt__')
        operator = self._valid_operators[self.operator]

        if self.right_param is not None:
            right_value = _get_parsed_value(self.right_param, self.right_use_calibrated_value)
        elif self.right_value is not None:
            t_left_param = type(left_value)  # Coerce right value xml representation to correct type
            right_value = t_left_param(self.right_value)
        else:
            raise ValueError(f"Error when evaluating condition {self}. Neither right_param nor right_value is set.")
        if left_value is None or right_value is None:
            raise ComparisonError(f"Error comparing {left_value} and {right_value}. Neither should be None.")

        # x.__le__(y) style call
        return getattr(left_value, operator)(right_value)


Anded = namedtuple('Anded', ['conditions', 'ors'])
Ored = namedtuple('Ored', ['conditions', 'ands'])


class BooleanExpression(MatchCriteria):
    """<xtce:BooleanExpression>"""

    def __init__(self, expression: Union[Condition, Anded, Ored]):
        self.expression = expression

    @classmethod
    def from_match_criteria_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'BooleanExpression':
        """Abstract classmethod to create a match criteria object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
           XML element
        ns : dict
           XML namespace dict

        Returns
        -------
        : BooleanExpression
        """

        def _parse_anded(anded_el: ElementTree.Element) -> Anded:
            """Create an Anded object from an xtce:ANDedConditions element

            Parameters
            ----------
            anded_el: ElementTree.Element
                xtce:ANDedConditions element

            Returns
            -------
            : Anded
            """
            conditions = [Condition.from_match_criteria_xml_element(el, ns)
                          for el in anded_el.findall('xtce:Condition', ns)]
            anded_ors = [_parse_ored(anded_or) for anded_or in anded_el.findall('xtce:ORedConditions', ns)]
            return Anded(conditions, anded_ors)

        def _parse_ored(ored_el: ElementTree.Element) -> Ored:
            """Create an Ored object from an xtce:ARedConditions element

            Parameters
            ----------
            ored_el: ElementTree.Element
                xtce:ORedConditions element

            Returns
            -------
            : Ored
            """
            conditions = [Condition.from_match_criteria_xml_element(el, ns)
                          for el in ored_el.findall('xtce:Condition', ns)]
            ored_ands = [_parse_anded(ored_and) for ored_and in ored_el.findall('xtce:ANDedConditions', ns)]
            return Ored(conditions, ored_ands)

        if element.find('xtce:Condition', ns) is not None:
            condition = Condition.from_match_criteria_xml_element(element.find('xtce:Condition', ns), ns)
            return cls(expression=condition)
        if element.find('xtce:ANDedConditions', ns) is not None:
            return cls(expression=_parse_anded(element.find('xtce:ANDedConditions', ns)))
        if element.find('xtce:ORedConditions', ns) is not None:
            return cls(expression=_parse_ored(element.find('xtce:ORedConditions', ns)))
        raise ValueError(f"Failed to parse {element}")

    def evaluate(self, parsed_data: dict, current_parsed_value: Optional[Union[int, float]] = None) -> bool:
        """Evaluate the criteria in the BooleanExpression down to a single boolean.

        Parameters
        ----------
        parsed_data : dict
            Dictionary of parsed parameter data so far. Used to evaluate truthyness of the match criteria.
        current_parsed_value : Optional[Union[int, float]]
            Current value being parsed.

        Returns
        -------
        : bool
            Truthyness of this match criteria based on parsed_data values.
        """

        def _or(ored: Ored):
            for condition in ored.conditions:
                if condition.evaluate(parsed_data) is True:
                    return True
            for anded in ored.ands:
                if _and(anded):
                    return True
            return False

        def _and(anded: Anded):
            for condition in anded.conditions:
                if condition.evaluate(parsed_data) is False:
                    return False
            for ored in anded.ors:
                if not _or(ored):
                    return False
            return True

        if isinstance(self.expression, Condition):
            return self.expression.evaluate(parsed_data)
        if isinstance(self.expression, Anded):
            return _and(self.expression)
        if isinstance(self.expression, Ored):
            return _or(self.expression)

        raise ValueError(f"Error evaluating an unknown expression {self.expression}.")


class DiscreteLookup(AttrComparable):
    """<xtce:DiscreteLookup>"""

    def __init__(self, match_criteria: list, lookup_value: Union[int, float]):
        """Constructor

        Parameters
        ----------
        match_criteria : list
            List of criteria to determine if the lookup value should be returned during evaluation.
        lookup_value : Union[int, float]
            Value to return from the lookup if the criteria evaluate true
        """
        self.match_criteria = match_criteria
        self.lookup_value = lookup_value

    @classmethod
    def from_discrete_lookup_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'DiscreteLookup':
        """Create a DiscreteLookup object from an <xtce:DiscreteLookup> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:DiscreteLookup> XML element from which to parse the DiscreteLookup object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : DiscreteLookup
        """
        lookup_value = float(element.attrib['value'])
        if element.find('xtce:ComparisonList', ns) is not None:
            match_criteria = [Comparison.from_match_criteria_xml_element(el, ns)
                              for el in element.findall('xtce:ComparisonList/xtce:Comparison', ns)]
        elif element.find('xtce:Comparison', ns) is not None:
            match_criteria = [Comparison.from_match_criteria_xml_element(
                element.find('xtce:Comparison', ns), ns)]
        else:
            raise NotImplementedError("Only Comparison and ComparisonList are implemented for DiscreteLookup.")

        return cls(match_criteria, lookup_value)

    def evaluate(self, parsed_data: dict, current_parsed_value: Optional[Union[int, float]] = None) -> Any:
        """Evaluate the lookup to determine if it is valid.

        Parameters
        ----------
        parsed_data : dict
            Data parsed so far (for referencing during criteria evaluation).
        current_parsed_value: Optional[Union[int, float]]
            If referenced parameter in criterion isn't in parsed_data dict, we assume we are comparing against this
            currently parsed value.

        Returns
        -------
        : any
            Return the lookup value if the match criteria evaluate true. Return None otherwise.
        """
        if all(criterion.evaluate(parsed_data, current_parsed_value) for criterion in self.match_criteria):
            # If the parsed data so far satisfy all the match criteria
            return self.lookup_value
        return None


# Calibrator definitions
class Calibrator(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE calibrators"""

    @classmethod
    @abstractmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'Calibrator':
        """Abstract classmethod to create a default_calibrator object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        return NotImplemented

    @abstractmethod
    def calibrate(self, uncalibrated_value: Union[int, float]) -> Union[int, float]:
        """Takes an integer-encoded or float-encoded value and returns a calibrated version.

        Parameters
        ----------
        uncalibrated_value : Union[int, float]
            The uncalibrated, raw encoded value

        Returns
        -------
        : Union[int, float]
            Calibrated value
        """
        raise NotImplementedError


SplinePoint = namedtuple('SplinePoint', ['raw', 'calibrated'])


class SplineCalibrator(Calibrator):
    """<xtce:SplineCalibrator>"""
    _order_mapping = {'zero': 0, 'first': 1, 'second': 2, 'third': 3}

    def __init__(self, points: list, order: int = 0, extrapolate: bool = False):
        """Constructor

        Parameters
        ----------
        points : list
            List of SplinePoint objects. These points are sorted by their raw values on instantiation.
        order : int
            Spline order. Only zero and first order splines are supported.
        extrapolate : bool
            Whether or not to allow extrapolation outside the bounds of the spline points. If False, raises an
            error when calibrate is called for a query point outside the bounds of the spline points.
        """
        if order > 1:
            raise NotImplementedError("Spline calibrators of order > 1 are not implemented. Consider contributing "
                                      "if you need this functionality. It does not appear to be commonly used but "
                                      "it probably would not be too hard to implement.")
        self.order = order
        self.points = sorted(points, key=lambda point: point.raw)  # Sort points before storing
        self.extrapolate = extrapolate

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'SplineCalibrator':
        """Create a spline default_calibrator object from an <xtce:SplineCalibrator> XML element."""
        point_elements = element.findall('xtce:SplinePoint', ns)
        spline_points = [
            SplinePoint(raw=float(p.attrib['raw']), calibrated=float(p.attrib['calibrated']))
            for p in point_elements
        ]
        order = int(cls._order_mapping[element.attrib['order']]) if 'order' in element.attrib else 0
        extrapolate = element.attrib['extrapolate'].lower() == 'true' if 'extrapolate' in element.attrib else False
        return cls(order=order, points=spline_points, extrapolate=extrapolate)

    def calibrate(self, uncalibrated_value: float) -> float:
        """Take an integer-encoded value and returns a calibrated version according to the spline points.

        Parameters
        ----------
        uncalibrated_value : float
            Query point.

        Returns
        -------
        : float
            Calibrated value
        """
        if self.order == 0:
            return self._zero_order_spline_interp(uncalibrated_value)
        if self.order == 1:
            return self._first_order_spline_interp(uncalibrated_value)
        raise NotImplementedError(f"SplineCalibrator is not implemented for spline order {self.order}.")

    def _zero_order_spline_interp(self, query_point: float) -> float:
        """Abstraction for zero order spline interpolation. If extrapolation is set to a truthy value, we use
        the nearest point to extrapolate outside the range of the given spline points. Within the range of spline
        points, we use nearest lower point interpolation.

        Parameters
        ----------
        query_point : float
            Query point.

        Returns
        -------
        : float
            Calibrated value.
        """
        x = [float(p.raw) for p in self.points]
        y = [float(p.calibrated) for p in self.points]
        if min(x) <= query_point <= max(x):
            first_greater = [p.raw > query_point for p in self.points].index(True)
            return y[first_greater - 1]
        if query_point > max(x) and self.extrapolate:
            return y[-1]
        if query_point < min(x) and self.extrapolate:
            return y[0]
        raise CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                               f"{query_point} falls outside the range of spline points {self.points}")

    def _first_order_spline_interp(self, query_point: float) -> float:
        """Abstraction for first order spline interpolation. If extrapolation is set to a truthy value, we use the
        end points to make a linear function and use it to extrapolate.

        Parameters
        ----------
        query_point : float
            Query point.

        Returns
        -------
        float
            Calibrated value.
        """

        def linear_func(xq: float, x0: float, x1: float, y0: float, y1: float) -> float:
            """Evaluate a linear function through points (x0, y0), (x1, y1) at point xq

            Parameters
            ----------
            xq : float
            x0 : float
            x1 : float
            y0 : float
            y1 : float

            Returns
            -------
            yq : float
                Interpolated point
            """
            slope = (y1 - y0) / (x1 - x0)
            return (slope * (xq - x0)) + y0

        x = [p.raw for p in self.points]
        y = [p.calibrated for p in self.points]
        if min(x) <= query_point <= max(x):
            first_greater = [p.raw > query_point for p in self.points].index(True)
            return linear_func(query_point,
                               x[first_greater - 1], x[first_greater],
                               y[first_greater - 1], y[first_greater])
        if query_point > max(x) and self.extrapolate:
            return linear_func(query_point, x[-2], x[-1], y[-2], y[-1])
        if query_point < min(x) and self.extrapolate:
            return linear_func(query_point, x[0], x[1], y[0], y[1])
        raise CalibrationError(f"Extrapolation is set to a falsy value ({self.extrapolate}) but query value "
                               f"{query_point} falls outside the range of spline points {self.points}")


PolynomialCoefficient = namedtuple('PolynomialCoefficient', ['coefficient', 'exponent'])


class PolynomialCalibrator(Calibrator):
    """<xtce:PolynomialCalibrator>"""

    def __init__(self, coefficients: list):
        """Constructor

        Parameters
        ----------
        coefficients : list
            List of PolynomialCoefficient objects that define the polynomial.
        """
        self.coefficients = coefficients  # Coefficients should be a list of PolynomialCoefficients

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'PolynomialCalibrator':
        """Create a polynomial default_calibrator object from an <xtce:PolynomialCalibrator> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:PolynomialCalibrator> XML element
        ns : dict
            Namespace dict

        Returns
        -------

        """
        terms = element.findall('xtce:Term', ns)
        coefficients = [
            PolynomialCoefficient(coefficient=float(term.attrib['coefficient']), exponent=int(term.attrib['exponent']))
            for term in terms
        ]
        return cls(coefficients=coefficients)

    def calibrate(self, uncalibrated_value: float) -> float:
        """Evaluate the polynomial defined by object coefficients at the specified uncalibrated point.

        Parameters
        ----------
        uncalibrated_value : float
            Query point.

        Returns
        -------
        float
            Calibrated value
        """
        return sum(a * (uncalibrated_value ** n) for a, n in self.coefficients)


class MathOperationCalibrator(Calibrator):
    """<xtce:MathOperationCalibrator>"""
    err_msg = "The MathOperationCalibrator element is not supported in this package but pull requests are welcome!"

    def __init__(self):
        """Constructor

        Not implemented.
        """
        raise NotImplementedError(self.err_msg)

    @classmethod
    def from_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'MathOperationCalibrator':
        """Create a math operation default_calibrator from an <xtce:MathOperationCalibrator> XML element."""
        raise NotImplementedError(cls.err_msg)

    def calibrate(self, uncalibrated_value: int):
        """Stub

        Parameters
        ----------
        uncalibrated_value

        Returns
        -------

        """
        raise NotImplementedError(self.err_msg)


class ContextCalibrator(AttrComparable):
    """<xtce:ContextCalibrator>"""

    def __init__(self, match_criteria: list, calibrator: Calibrator):
        """Constructor

        Parameters
        ----------
        match_criteria : Union[MatchCriteria, list]
            Object representing the logical operations to be performed to determine whether to use this
            default_calibrator. This can be a Comparison, a ComparsonList (a list of Comparison objects),
            a BooleanExpression (not supported), or a CustomAlgorithm (not supported)
        calibrator : Calibrator
            Calibrator to use if match criteria evaluates to True
        """
        self.match_criteria = match_criteria
        self.calibrator = calibrator

    @staticmethod
    def get_context_match_criteria(element: ElementTree.Element, ns: dict) -> List[MatchCriteria]:
        """Parse contextual requirements from a Comparison, ComparisonList, or BooleanExpression

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : List[MatchCriteria]
            List of Comparisons that can be evaluated to determine whether this calibrator should be used.
        """
        context_match_element = element.find('xtce:ContextMatch', ns)
        if context_match_element.find('xtce:ComparisonList', ns) is not None:
            return [Comparison.from_match_criteria_xml_element(el, ns)
                    for el in context_match_element.findall('xtce:ComparisonList/xtce:Comparison', ns)]
        if context_match_element.find('xtce:Comparison', ns) is not None:
            return [Comparison.from_match_criteria_xml_element(
                context_match_element.find('xtce:Comparison', ns), ns)]
        if context_match_element.find('xtce:BooleanExpression', ns) is not None:
            return [BooleanExpression.from_match_criteria_xml_element(
                context_match_element.find('xtce:BooleanExpression', ns), ns)]
        raise NotImplementedError("ContextCalibrator doesn't contain Comparison, ComparisonList, or BooleanExpression. "
                                  "This probably means the match criteria is an unsupported type "
                                  "(CustomAlgorithm).")

    @classmethod
    def from_context_calibrator_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'ContextCalibrator':
        """Create a ContextCalibrator object from an <xtce:ContextCalibrator> XML element

        Parameters
        ----------
        element : ElementTree.Element
            <xtce:ContextCalibrator> XML element from which to parse the ContextCalibrator object.
        ns : dict
            Namespace dict for XML parsing

        Returns
        -------
        : cls
        """
        match_criteria = cls.get_context_match_criteria(element, ns)

        if element.find('xtce:Calibrator/xtce:SplineCalibrator', ns) is not None:
            calibrator = SplineCalibrator.from_calibrator_xml_element(
                element.find('xtce:Calibrator/xtce:SplineCalibrator', ns), ns)
        elif element.find('xtce:Calibrator/xtce:PolynomialCalibrator', ns):
            calibrator = PolynomialCalibrator.from_calibrator_xml_element(
                element.find('xtce:Calibrator/xtce:PolynomialCalibrator', ns), ns)
        else:
            raise NotImplementedError(
                "Unsupported default_calibrator type. space_packet_parser only supports Polynomial and Spline"
                "calibrators for ContextCalibrators.")

        return cls(match_criteria=match_criteria, calibrator=calibrator)

    def calibrate(self, parsed_value: Union[int, float]) -> Union[int, float]:
        """Wrapper method for the internal `Calibrator.calibrate`

        Parameters
        ----------
        parsed_value : Union[int, float]
            Uncalibrated value.

        Returns
        -------
        : Union[int, float]
            Calibrated value
        """
        return self.calibrator.calibrate(parsed_value)


@dataclass
class Packet:
    """CCSDS Packet

    Can be parsed to populate data items. This ``Packet`` class keeps track
    of the current parsing position for know where to read from next when
    parsing data items.

    Parameters
    ----------
    data : bytes
        The binary data for a single packet.
    pos : int
        The bit cursor position in the packet. Default 0.
    """
    rawdata: bytes
    pos: Optional[int] = 0
    parsed_data: Optional[dict] = field(default_factory=lambda: {})

    def __len__(self):
        """The length of the full packet data object in bits."""
        return len(self.rawdata) * 8

    @property
    def header(self):
        """Parsed header data items."""
        return dict(list(self.parsed_data.items())[:7])

    @property
    def data(self):
        """Parsed user data items."""
        return dict(list(self.parsed_data.items())[7:])

    def read_as_bytes(self, nbits: int) -> bytes:
        """Read a number of bits from the packet data as bytes.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : bytes
            Raw bytes from the packet data
        """
        if self.pos + nbits > len(self):
            raise ValueError("End of packet reached")
        if self.pos % 8 == 0 and nbits % 8 == 0:
            # If the read is byte-aligned, we can just return the bytes directly
            data = self.rawdata[self.pos//8:self.pos//8 + nbits // 8]
            self.pos += nbits
            return data
        # We are non-byte aligned, so we need to extract the bits and convert to bytes
        bytes_as_int = _extract_bits(self.rawdata, self.pos, nbits)
        self.pos += nbits
        return int.to_bytes(bytes_as_int, (nbits + 7) // 8, "big")

    def read_as_int(self, nbits: int) -> int:
        """Read a number of bits from the packet data as an integer.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : int
            Integer representation of the bits read from the packet
        """
        int_data = _extract_bits(self.rawdata, self.pos, nbits)
        self.pos += nbits
        return int_data


# DataEncoding definitions
class DataEncoding(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE data encodings"""

    @classmethod
    @abstractmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'DataEncoding':
        """Abstract classmethod to create a data encoding object from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : DataEncoding
        """
        return NotImplemented

    @staticmethod
    def get_default_calibrator(data_encoding_element: ElementTree.Element, ns: dict) -> Union[Calibrator, None]:
        """Gets the default_calibrator for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            The data encoding element which should contain the default_calibrator
        ns : dict
            XML namespace dict

        Returns
        -------
        : Union[Calibrator, None]
        """
        for calibrator in [SplineCalibrator, PolynomialCalibrator, MathOperationCalibrator]:
            # Try to find each type of data encoding element. If we find one, we assume it's the only one.
            element = data_encoding_element.find(f"xtce:DefaultCalibrator/xtce:{calibrator.__name__}", ns)
            if element is not None:
                return calibrator.from_calibrator_xml_element(element, ns)
        return None

    @staticmethod
    def get_context_calibrators(
            data_encoding_element: ElementTree.Element, ns: dict) -> Union[List[ContextCalibrator], None]:
        """Get the context default_calibrator(s) for the data encoding element

        Parameters
        ----------
        data_encoding_element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : Union[List[ContextCalibrator], None]
            List of ContextCalibrator objects or None if there are no context calibrators
        """
        if data_encoding_element.find('xtce:ContextCalibratorList', ns):
            context_calibrators_elements = data_encoding_element.findall(
                'xtce:ContextCalibratorList/xtce:ContextCalibrator', ns)
            return [ContextCalibrator.from_context_calibrator_xml_element(el, ns)
                    for el in context_calibrators_elements]
        return None

    @staticmethod
    def _get_linear_adjuster(parent_element: ElementTree.Element, ns: dict) -> Union[callable, None]:
        """Examine a parent (e.g. a <xtce:DynamicValue>) element and find a LinearAdjustment if present,
        creating and returning a function that evaluates the adjustment.

        Parameters
        ----------
        parent_element : ElementTree.Element
            Parent element which may contain a LinearAdjustment
        ns : dict
            XML namespace dict

        Returns
        -------
        adjuster : Union[callable, None]
            Function object that adjusts a SizeInBits value by a linear function or None if no adjuster present
        """
        linear_adjustment_element = parent_element.find('xtce:LinearAdjustment', ns)
        if linear_adjustment_element is not None:
            slope = (int(linear_adjustment_element.attrib['slope'])
                     if 'slope' in linear_adjustment_element.attrib else 0)
            intercept = (int(linear_adjustment_element.attrib['intercept'])
                         if 'intercept' in linear_adjustment_element.attrib else 0)

            def adjuster(x: int) -> int:
                """Perform a linear adjustment to a size parameter

                Parameters
                ----------
                x : int
                    Unadjusted size parameter.

                Returns
                -------
                : int
                    Adjusted size parameter
                """
                adjusted = (slope * float(x)) + intercept
                if not adjusted.is_integer():
                    raise ValueError(f"Error when adjusting a value with a LinearAdjustment. Got y=mx + b as "
                                     f"{adjusted}={slope}*{x}+{intercept} returned a float. "
                                     f"Should have been an int.")
                return int(adjusted)

            return adjuster
        return None

    def _calculate_size(self, packet: Packet) -> int:
        """Calculate the size of the data item in bits.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : int
            Size of the data item in bits.
        """
        raise NotImplementedError()

    def parse_value(self, packet: Packet, **kwargs) -> Tuple[Any, Any]:
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        Returns
        -------
        : any
            Raw value
        : any
            Calibrated value
        """
        raise NotImplementedError()


class StringDataEncoding(DataEncoding):
    """<xtce:StringDataEncoding>"""

    _supported_encodings = ('US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8', 'UTF-16',
                            'UTF-16LE', 'UTF-16BE', 'UTF-32', 'UTF-32LE', 'UTF-32BE')

    def __init__(self, encoding: str = 'UTF-8',
                 byte_order: Optional[str] = None,
                 termination_character: Optional[str] = None,
                 fixed_length: Optional[int] = None,
                 leading_length_size: Optional[int] = None,
                 dynamic_length_reference: Optional[str] = None,
                 use_calibrated_value: Optional[bool] = True,
                 discrete_lookup_length: Optional[List[DiscreteLookup]] = None,
                 length_linear_adjuster: Optional[callable] = None):
        # pylint: disable=pointless-statement
        f"""Constructor
        Only one of termination_character, fixed_length, or leading_length_size should be set. Setting more than one
        is nonsensical.

        Parameters
        ----------
        encoding : str
            One of the XTCE-supported encodings: {self._supported_encodings}
            Describes how to read the characters in the string.
            Default is UTF-8.
        byte_order : Optional[str]
            Description of the byte order, used for multi-byte character encodings where the endianness cannot be
            determined from the encoding specifier. Can be None if encoding is single-byte or UTF-*BE/UTF-*LE.
        termination_character : Optional[str]
            A single hexadecimal character, represented as a string. Must be encoded in the same encoding as the string
            itself. For example, for a utf-8 encoded string, the hex string must be two hex characters (one byte).
            For a UTF-16* encoded string, the hex representation of the termination character must be four characters
            (two bytes).
        fixed_length : Optional[int]
            Fixed length of the string, in bits.
        leading_length_size : Optional[int]
            Fixed size in bits of a leading field that contains the length of the subsequent string.
        dynamic_length_reference : Optional[str]
            Name of referenced parameter for dynamic length, in bits. May be combined with a linear_adjuster
        use_calibrated_value: Optional[bool]
            Whether to use the calibrated value on the referenced parameter in dynamic_length_reference.
            Default is True.
        discrete_lookup_length : Optional[List[DiscreteLookup]]
            List of DiscreteLookup objects with which to determine string length from another parameter.
        length_linear_adjuster : Optional[callable]
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        if encoding not in self._supported_encodings:
            raise ValueError(f"Got encoding={encoding} (uppercased). "
                             f"Encoding must be one of {self._supported_encodings}.")
        self.encoding = encoding
        if encoding not in ['US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8']:  # for these, byte order doesn't matter
            if byte_order is None:
                if "LE" in encoding:
                    self.byte_order = "leastSignificantByteFirst"
                elif "BE" in encoding:
                    self.byte_order = "mostSignificantByteFirst"
                else:
                    raise ValueError("Byte order must be specified for multi-byte character encodings.")
            else:
                self.byte_order = byte_order
        self.termination_character = termination_character
        if termination_character:
            # Always in hex, per 4.3.2.2.5.5.4 of XTCE spec
            self.termination_character = bytes.fromhex(termination_character)
            # Check that the termination character is a single character in the specified encoding
            # e.g. b'\x58' in utf-8 is "X"
            # b'\x21\00' in utf-16-le is "!"
            # b'\x00\x21' in utf-16-be is "!"
            if len(self.termination_character.decode(encoding)) != 1:
                raise ValueError(f"Termination character {termination_character} appears to be malformed. "
                                 f"Expected a hex string representation of a single character, e.g. '58' for "
                                 f"character 'X' in utf-8 or '5800' for character 'X' in utf-16-le. Note that "
                                 f"variable-width encoding is not yet supported in any encoding.")
        self.fixed_length = fixed_length
        self.leading_length_size = leading_length_size
        self.dynamic_length_reference = dynamic_length_reference
        self.use_calibrated_value = use_calibrated_value
        self.discrete_lookup_length = discrete_lookup_length
        self.length_linear_adjuster = length_linear_adjuster

    def _calculate_size(self, packet: Packet) -> int:
        """Calculate the length of the string data item in bits.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : int
            Number of bits in the string data item
        """
        # pylint: disable=too-many-branches
        if self.fixed_length:
            strlen_bits = self.fixed_length
        elif self.leading_length_size is not None:  # strlen_bits is determined from a preceding integer
            strlen_bits = packet.read_as_int(self.leading_length_size)
            if strlen_bits % 8 != 0:
                warnings.warn(f"String length (in bits) is {strlen_bits}, which is not a multiple of 8. "
                              f"This likely means something is wrong since strings are expected to be integer numbers "
                              f"of bytes.")
        elif self.discrete_lookup_length is not None:
            for discrete_lookup in self.discrete_lookup_length:
                strlen_bits = discrete_lookup.evaluate(packet.parsed_data)
                if strlen_bits is not None:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {packet}.')
        elif self.dynamic_length_reference is not None:
            if self.use_calibrated_value is True:
                strlen_bits = packet.parsed_data[self.dynamic_length_reference].derived_value
            else:
                strlen_bits = packet.parsed_data[self.dynamic_length_reference].raw_value
            strlen_bits = int(strlen_bits)
        elif self.termination_character is not None:
            # Look through the rest of the packet data to find the termination character
            nbits_left = len(packet) - packet.pos
            orig_pos = packet.pos
            string_buffer = packet.read_as_bytes(nbits_left - nbits_left % 8)
            # Reset the original position because we only wanted to look ahead
            packet.pos = orig_pos
            try:
                strlen_bits = string_buffer.index(self.termination_character) * 8
            except ValueError as exc:
                # Termination character not found in the string buffer
                raise ValueError(f"Reached the end of the packet data without finding the "
                                 f"termination character {self.termination_character}") from exc
        else:
            raise ValueError("Unable to parse StringParameterType. "
                             "Didn't contain any way to constrain the length of the string.")
        if not self.termination_character and self.length_linear_adjuster is not None:
            # Only adjust if we are not doing this by termination character. Adjusting a length that is objectively
            # determined via termination character is nonsensical.
            strlen_bits = self.length_linear_adjuster(strlen_bits)
        return strlen_bits
        # pylint: enable=too-many-branches

    def parse_value(self, packet: Packet, **kwargs) -> Tuple[str, None]:
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        Returns
        -------
        : str
            Parsed value
        : None
            Calibrated value
        """
        nbits = self._calculate_size(packet)
        parsed_value = packet.read_as_bytes(nbits)
        if self.termination_character is not None:
            # We need to skip over the termination character if there was one
            packet.pos += len(self.termination_character) * 8
        return parsed_value.decode(self.encoding), None

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'StringDataEncoding':
        """Create a data encoding object from an <xtce:StringDataEncoding> XML element.
        Strings in XTCE can be described in three ways:

        1. Using a termination character that marks the end of the string.
        2. Using a fixed length, which may be derived from referenced parameter either directly or via a discrete
           lookup table.
        3. Using a leading size field that describes the size of the following string.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        cls
        """
        encoding: str = element.get("encoding", "UTF-8")

        byte_order = None  # fallthrough value
        if encoding not in ('US-ASCII', 'ISO-8859-1', 'Windows-1252', 'UTF-8'):  # single-byte chars
            if not (encoding.endswith("BE") or encoding.endswith("LE")):
                byte_order = element.get("byteOrder")
                if byte_order is None:
                    raise ValueError("For multi-byte character encodings, byte order must be specified "
                                     "either using the byteOrder attribute or via the encoding itself.")

        try:
            termination_character = element.find('xtce:SizeInBits/xtce:TerminationChar', ns).text
            return cls(termination_character=termination_character, encoding=encoding, byte_order=byte_order)
        except AttributeError:
            pass

        try:
            leading_length_size = int(
                element.find('xtce:SizeInBits/xtce:LeadingSize', ns).attrib['sizeInBitsOfSizeTag'])
            return cls(leading_length_size=leading_length_size, encoding=encoding, byte_order=byte_order)
        except AttributeError:
            pass

        fixed_element = element.find('xtce:SizeInBits/xtce:Fixed', ns)

        discrete_lookup_list_element = fixed_element.find('xtce:DiscreteLookupList', ns)
        if discrete_lookup_list_element is not None:
            discrete_lookup_list = [DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                    for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
            return cls(encoding=encoding, byte_order=byte_order,
                       discrete_lookup_length=discrete_lookup_list)

        try:
            dynamic_value_element = fixed_element.find('xtce:DynamicValue', ns)
            referenced_parameter = dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib['parameterRef']
            use_calibrated_value = True
            if 'useCalibratedValue' in dynamic_value_element.find('xtce:ParameterInstanceRef', ns).attrib:
                use_calibrated_value = dynamic_value_element.find(
                    'xtce:ParameterInstanceRef', ns).attrib['useCalibratedValue'].lower() == "true"
            linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
            return cls(encoding=encoding, byte_order=byte_order,
                       dynamic_length_reference=referenced_parameter, use_calibrated_value=use_calibrated_value,
                       length_linear_adjuster=linear_adjuster)
        except AttributeError:
            pass

        try:
            fixed_length = int(fixed_element.find('xtce:FixedValue', ns).text)
            return cls(fixed_length=fixed_length, encoding=encoding, byte_order=byte_order)
        except AttributeError:
            pass

        raise ElementNotFoundError(f"Failed to parse StringDataEncoding for element {ElementTree.tostring(element)}")


class NumericDataEncoding(DataEncoding, metaclass=ABCMeta):
    """Abstract class that is inherited by IntegerDataEncoding and FloatDataEncoding"""

    def __init__(self, size_in_bits: int,
                 encoding: str,
                 byte_order: str = "mostSignificantByteFirst",
                 default_calibrator: Optional[Calibrator] = None,
                 context_calibrators: Optional[List[ContextCalibrator]] = None):
        """Constructor

        Parameters
        ----------
        size_in_bits : int
            Size of the integer
        encoding : str
            String indicating the type of encoding for the integer. FSW seems to use primarily 'signed' and 'unsigned',
            though 'signed' is not actually a valid specifier according to XTCE. 'twosCompliment' [sic] should be used
            instead, though we support the unofficial 'signed' specifier here.
            For supported specifiers, see XTCE spec 4.3.2.2.5.6.2
        byte_order : str
            Description of the byte order. Default is 'mostSignficantByteFirst' (big-endian).
        default_calibrator : Optional[Calibrator]
            Optional Calibrator object, containing information on how to transform the integer-encoded data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : Optional[List[ContextCalibrator]]
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        self.size_in_bits = size_in_bits
        self.encoding = encoding
        self.byte_order = byte_order
        self.default_calibrator = default_calibrator
        self.context_calibrators = context_calibrators

    def _calculate_size(self, packet: Packet) -> int:
        return self.size_in_bits

    @abstractmethod
    def _get_raw_value(self, packet: Packet) -> Union[int, float]:
        """Read the raw value from the packet data

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        : int
            Raw value
        """
        raise NotImplementedError()

    @staticmethod
    def _twos_complement(val: int, bit_width: int) -> int:
        """Take the twos complement of val

        Used when parsing ints and some floats
        """
        if (val & (1 << (bit_width - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
            return val - (1 << bit_width)  # compute negative value
        return val

    def parse_value(self,
                    packet: Packet,
                    **kwargs) -> Tuple[Union[int, float], Union[int, float]]:
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        parsed_value = self._get_raw_value(packet)
        # Attempt to calibrate
        calibrated_value = parsed_value  # Provides a fall through in case we have no calibrators
        if self.context_calibrators:
            for calibrator in self.context_calibrators:
                match_criteria = calibrator.match_criteria
                if all(criterion.evaluate(packet.parsed_data, parsed_value) for criterion in match_criteria):
                    # If the parsed data so far satisfy all the match criteria
                    calibrated_value = calibrator.calibrate(parsed_value)
                    return parsed_value, calibrated_value
        if self.default_calibrator:  # If no context calibrators or if none apply and there is a default
            calibrated_value = self.default_calibrator.calibrate(parsed_value)
        # Ultimate fallthrough
        return parsed_value, calibrated_value


class IntegerDataEncoding(NumericDataEncoding):
    """<xtce:IntegerDataEncoding>"""

    def _get_raw_value(self, packet: Packet) -> int:
        # Extract the bits from the data in big-endian order from the packet
        val = packet.read_as_int(self.size_in_bits)
        if self.byte_order == 'leastSignificantByteFirst':
            # Convert little-endian (LSB first) int to bigendian. Just reverses the order of the bytes.
            val = int.from_bytes(
                val.to_bytes(
                    length=(self.size_in_bits + 7) // 8,
                    byteorder="little"
                ),
                byteorder="big"
            )
        if self.encoding == 'unsigned':
            return val
        # It is a signed integer, and we need to take into account the first bit
        return self._twos_complement(val, self.size_in_bits)

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'IntegerDataEncoding':
        """Create a data encoding object from an <xtce:IntegerDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        encoding = element.attrib['encoding'] if 'encoding' in element.attrib else "unsigned"
        byte_order = element.get("byteOrder", "mostSignificantByteFirst")
        calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding, byte_order=byte_order,
                   default_calibrator=calibrator, context_calibrators=context_calibrators)


class FloatDataEncoding(NumericDataEncoding):
    """<xtce:FloatDataEncoding>"""
    _supported_encodings = ['IEEE-754', 'MIL-1750A']

    def __init__(self, size_in_bits: int, encoding: str = 'IEEE-754',
                 byte_order: str = 'mostSignificantByteFirst',
                 default_calibrator: Optional[Calibrator] = None,
                 context_calibrators: Optional[List[ContextCalibrator]] = None):
        """Constructor

        Parameters
        ----------
        size_in_bits : int
            Size of the encoded value, in bits.
        encoding : str
            Encoding method of the float data. Must be either 'IEEE-754' or 'MIL-1750A'. Defaults to IEEE-754.
        byte_order : str
            Description of the byte order. Default is 'mostSignificantByteFirst' (big endian).
        default_calibrator : Optional[Calibrator]
            Optional Calibrator object, containing information on how to transform the data, e.g. via
            a polynomial conversion or spline interpolation.
        context_calibrators : Optional[List[ContextCalibrator]]
            List of ContextCalibrator objects, containing match criteria and corresponding calibrators to use in
            various scenarios, based on other parameters.
        """
        if encoding not in self._supported_encodings:
            raise ValueError(f"Invalid encoding type {encoding} for float data. "
                             f"Must be one of {self._supported_encodings}.")
        if encoding == 'MIL-1750A' and size_in_bits != 32:
            raise ValueError("MIL-1750A encoded floats must be 32 bits, per the MIL-1750A spec. See "
                             "https://www.xgc-tek.com/manuals/mil-std-1750a/c191.html#AEN324")
        if encoding == 'IEEE-754' and size_in_bits not in (16, 32, 64):
            raise ValueError(f"Invalid size_in_bits value for IEEE-754 FloatDataEncoding, {size_in_bits}. "
                             "Must be 16, 32, or 64.")
        super().__init__(size_in_bits, encoding=encoding, byte_order=byte_order,
                         default_calibrator=default_calibrator, context_calibrators=context_calibrators)

        if self.encoding == "MIL-1750A":
            def _mil_parse_func(mil_bytes: bytes):
                """Parsing function for MIL-1750A floats"""
                # MIL 1750A floats are always 32 bit
                # See: https://www.xgc-tek.com/manuals/mil-std-1750a/c191.html#AEN324
                #
                #  MSB                                         LSB MSB          LSB
                # ------------------------------------------------------------------
                # | S|                   Mantissa                 |    Exponent    |
                # ------------------------------------------------------------------
                #   0  1                                        23 24            31
                if self.byte_order == "mostSignificantByteFirst":
                    bytes_as_int = int.from_bytes(mil_bytes, byteorder='big')
                else:
                    bytes_as_int = int.from_bytes(mil_bytes, byteorder='little')
                exponent = bytes_as_int & 0xFF  # last 8 bits
                mantissa = (bytes_as_int >> 8) & 0xFFFFFF  # bits 0 through 23 (24 bits)
                # We include the sign bit with the mantissa because we can just take the twos complement
                # of it directly and use it in the final calculation for the value

                # Both mantissa and exponent are stored as twos complement with no bias
                exponent = self._twos_complement(exponent, 8)
                mantissa = self._twos_complement(mantissa, 24)

                # Calculate float value using native Python floats, which are more precise
                return mantissa * (2.0 ** (exponent - (24 - 1)))

            # Set up the parsing function just once, so we can use it repeatedly with _get_raw_value
            self.parse_func = _mil_parse_func
        else:
            if self.byte_order == "leastSignificantByteFirst":
                self._struct_format = "<"
            else:
                # Big-endian is the default
                self._struct_format = ">"

            if self.size_in_bits == 16:
                self._struct_format += "e"
            elif self.size_in_bits == 32:
                self._struct_format += "f"
            elif self.size_in_bits == 64:
                self._struct_format += "d"

            def ieee_parse_func(data: bytes):
                """Parsing function for IEEE floats"""
                # The packet data we got back is always extracted in big-endian order
                # but the struct format code contains the endianness of the float data
                return struct.unpack(self._struct_format, data)[0]

            # Set up the parsing function just once, so we can use it repeatedly with _get_raw_value
            self.parse_func: callable = ieee_parse_func

    def _get_raw_value(self, packet):
        """Read the data in as bytes and return a float representation."""
        data = packet.read_as_bytes(self.size_in_bits)
        # The parsing function is fully set during initialization to save time during parsing
        return self.parse_func(data)

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'FloatDataEncoding':
        """Create a data encoding object from an <xtce:FloatDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : cls
        """
        size_in_bits = int(element.attrib['sizeInBits'])
        encoding = element.get("encoding", "IEEE-754")
        byte_order = element.get("byteOrder", "mostSignificantByteFirst")
        default_calibrator = cls.get_default_calibrator(element, ns)
        context_calibrators = cls.get_context_calibrators(element, ns)
        return cls(size_in_bits=size_in_bits, encoding=encoding, byte_order=byte_order,
                   default_calibrator=default_calibrator, context_calibrators=context_calibrators)


class BinaryDataEncoding(DataEncoding):
    """<xtce:BinaryDataEncoding>"""

    def __init__(self, fixed_size_in_bits: Optional[int] = None,
                 size_reference_parameter: Optional[str] = None, use_calibrated_value: bool = True,
                 size_discrete_lookup_list: Optional[List[DiscreteLookup]] = None,
                 linear_adjuster: Optional[callable] = None):
        """Constructor

        Parameters
        ----------
        fixed_size_in_bits : Optional[int]
            Fixed size for the binary field, in bits.
        size_reference_parameter : Optional[str]
            Name of a parameter to reference for the binary field length, in bits. Note that space often specifies these
            fields in byte length, not bit length. This should be taken care of by a LinearAdjuster element that simply
            instructs the value to be multiplied by 8 but that hasn't historically been implemented unfortunately.
        use_calibrated_value: bool, Optional
            Default True. If False, the size_reference_parameter is examined for its raw value.
        size_discrete_lookup_list: Optional[List[DiscreteLookup]]
            List of DiscreteLookup objects by which to determine the length of the binary data field. This suffers from
            the same bit/byte conversion problem as size_reference_parameter.
        linear_adjuster : Optional[callable]
            Function that linearly adjusts a size. e.g. if the size reference parameter gives a length in bytes, the
            linear adjuster should multiply by 8 to give the size in bits.
        """
        self.fixed_size_in_bits = fixed_size_in_bits
        self.size_reference_parameter = size_reference_parameter
        self.use_calibrated_value = use_calibrated_value
        self.size_discrete_lookup_list = size_discrete_lookup_list
        self.linear_adjuster = linear_adjuster

    def _calculate_size(self, packet: Packet) -> int:
        """Determine the number of bits in the binary field.

        Returns
        -------
        : Union[str, None]
            Format string in the bitstring format. e.g. bin:1024
        """
        if self.fixed_size_in_bits is not None:
            len_bits = self.fixed_size_in_bits
        elif self.size_reference_parameter is not None:
            field_length_reference = self.size_reference_parameter
            if self.use_calibrated_value:
                len_bits = packet.parsed_data[field_length_reference].derived_value
            else:
                len_bits = packet.parsed_data[field_length_reference].raw_value
        elif self.size_discrete_lookup_list is not None:
            for discrete_lookup in self.size_discrete_lookup_list:
                len_bits = discrete_lookup.evaluate(packet.parsed_data)
                if len_bits is not None:
                    break
            else:
                raise ValueError('List of discrete lookup values being used for determining length of '
                                 f'string {self} found no matches based on {packet.parsed_data}.')
        else:
            raise ValueError("Unable to parse BinaryDataEncoding. "
                             "No fixed size, dynamic size, or dynamic lookup size were provided.")

        if self.linear_adjuster is not None:
            len_bits = self.linear_adjuster(len_bits)
        return len_bits

    def parse_value(self, packet: Packet, word_size: Optional[int] = None, **kwargs):
        """Parse a value from packet data, possibly using previously parsed data items to inform parsing.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        word_size : Optional[int]
            Word size for encoded data. This is used to ensure that the cursor ends up at the end of the last word
            and ready to parse the next data field.

        Returns
        -------
        : any
            Parsed value
        : any
            Calibrated value
        """
        nbits = self._calculate_size(packet)
        parsed_value = packet.read_as_bytes(nbits)
        if word_size:
            cursor_position_in_word = packet.pos % word_size
            if cursor_position_in_word != 0:
                logger.debug(f"Adjusting cursor position to the end of a {word_size} bit word.")
                packet.pos += word_size - cursor_position_in_word
        return parsed_value, None

    @classmethod
    def from_data_encoding_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'BinaryDataEncoding':
        """Create a data encoding object from an <xtce:BinaryDataEncoding> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            XML element
        ns : dict
            XML namespace dict

        Returns
        -------
        : BinaryDataEncoding
        """
        fixed_value_element = element.find('xtce:SizeInBits/xtce:FixedValue', ns)
        if fixed_value_element is not None:
            fixed_size_in_bits = int(fixed_value_element.text)
            return cls(fixed_size_in_bits=fixed_size_in_bits)

        dynamic_value_element = element.find('xtce:SizeInBits/xtce:DynamicValue', ns)
        if dynamic_value_element is not None:
            param_inst_ref = dynamic_value_element.find('xtce:ParameterInstanceRef', ns)
            referenced_parameter = param_inst_ref.attrib['parameterRef']
            use_calibrated_value = True
            if 'useCalibratedValue' in param_inst_ref.attrib:
                use_calibrated_value = param_inst_ref.attrib['useCalibratedValue'].lower() == "true"
            linear_adjuster = cls._get_linear_adjuster(dynamic_value_element, ns)
            return cls(size_reference_parameter=referenced_parameter,
                       use_calibrated_value=use_calibrated_value, linear_adjuster=linear_adjuster)

        discrete_lookup_list_element = element.find('xtce:SizeInBits/xtce:DiscreteLookupList', ns)
        if discrete_lookup_list_element is not None:
            discrete_lookup_list = [DiscreteLookup.from_discrete_lookup_xml_element(el, ns)
                                    for el in discrete_lookup_list_element.findall('xtce:DiscreteLookup', ns)]
            return cls(size_discrete_lookup_list=discrete_lookup_list)

        raise ValueError("Tried parsing a binary parameter length using Fixed, Dynamic, and DiscreteLookupList "
                         "but failed. See 3.4.5 of the XTCE Green Book CCSDS 660.1-G-2.")


# ParameterType definitions
class ParameterType(AttrComparable, metaclass=ABCMeta):
    """Abstract base class for XTCE parameter types"""

    def __init__(self, name: str, encoding: DataEncoding, unit: Optional[str] = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding, StringDataEncoding, etc.
        unit : Optional[str]
            String describing the unit for the stored value.
        """
        self.name = name
        self.unit = unit
        self.encoding = encoding

    def __repr__(self):
        module = self.__class__.__module__
        qualname = self.__class__.__qualname__
        return f"<{module}.{qualname} {self.name}>"

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict) -> 'ParameterType':
        """Create a *ParameterType from an <xtce:*ParameterType> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : ParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        return cls(name, encoding, unit)

    @staticmethod
    def get_units(parameter_type_element: ElementTree.Element, ns: dict) -> Union[str, None]:
        """Finds the units associated with a parameter type element and parsed them to return a unit string.
        We assume only one <xtce:Unit> but this could be extended to support multiple units.
        See section 4.3.2.2.4 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[str, None]
            Unit string or None if no units are defined
        """
        # Assume we are not parsing a Time Parameter Type, which stores units differently
        units = parameter_type_element.findall('xtce:UnitSet/xtce:Unit', ns)
        # TODO: Implement multiple unit elements for compound unit definitions
        assert len(units) <= 1, f"Found {len(units)} <xtce:Unit> elements in a single <xtce:UnitSet>." \
                                f"This is supported in the standard but is rarely used " \
                                f"and is not yet supported by this library."
        if units:
            return " ".join([u.text for u in units])
        # Units are optional so return None if they aren't specified
        return None

    @staticmethod
    def get_data_encoding(parameter_type_element: ElementTree.Element, ns: dict) -> Union[DataEncoding, None]:
        """Finds the data encoding XML element associated with a parameter type XML element and parses
        it, returning an object representation of the data encoding.

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[DataEncoding, None]
            DataEncoding object or None if no data encoding is defined (which is probably an issue)
        """
        for data_encoding in [StringDataEncoding, IntegerDataEncoding, FloatDataEncoding, BinaryDataEncoding]:
            # Try to find each type of data encoding element. If we find one, we assume it's the only one.
            element = parameter_type_element.find(f".//xtce:{data_encoding.__name__}", ns)
            if element is not None:
                return data_encoding.from_data_encoding_xml_element(element, ns)
        return None

    def parse_value(self, packet: Packet, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        parsed_value : any
            Resulting parsed data value.
        """
        return self.encoding.parse_value(packet, **kwargs)


class StringParameterType(ParameterType):
    """<xtce:StringParameterType>"""

    def __init__(self, name: str, encoding: StringDataEncoding, unit: Optional[str] = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : StringDataEncoding
            Must be a StringDataEncoding object since strings can't be encoded other ways.
        unit : Optional[str]
            String describing the unit for the stored value.
        """
        if not isinstance(encoding, StringDataEncoding):
            raise ValueError("StringParameterType may only be instantiated with a StringDataEncoding encoding.")
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.encoding = encoding  # Clarifies to static analysis tools that self.encoding is type StringDataEncoding


class IntegerParameterType(ParameterType):
    """<xtce:IntegerParameterType>"""
    pass


class FloatParameterType(ParameterType):
    """<xtce:FloatParameterType>"""
    pass


class EnumeratedParameterType(ParameterType):
    """<xtce:EnumeratedParameterType>"""

    def __init__(self, name: str, encoding: DataEncoding, enumeration: dict, unit: Union[str, None] = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name.
        unit : str
            Unit string for stored value.
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding.
        enumeration : dict
            Lookup with label:value pairs matching encoded values to their enum labels.
        """
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.enumeration = enumeration

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create an EnumeratedParameterType from an <xtce:EnumeratedParameterType> XML element.
        Overrides ParameterType.from_parameter_type_xml_element

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : EnumeratedParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        enumeration = cls.get_enumeration_list_contents(element, ns)
        return cls(name, encoding, enumeration=enumeration, unit=unit)

    @staticmethod
    def get_enumeration_list_contents(element: ElementTree.Element, ns: dict) -> dict:
        """Finds the <xtce:EnumerationList> element child of an <xtce:EnumeratedParameterType> and parses it,
        returning a dict. This method is confusingly named as if it might return a list. Sorry, XML and python
        semantics are not always compatible. It's called an enumeration list because the XML element is called
        <xtce:EnumerationList> but it contains key value pairs, so it's best represeneted as a dict.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to search for EnumerationList tags
        ns : dict
            XML namespace dict

        Returns
        -------
        : dict
        """
        enumeration_list = element.find('xtce:EnumerationList', ns)
        if enumeration_list is None:
            raise ValueError("An EnumeratedParameterType must contain an EnumerationList.")

        return {
            int(el.attrib['value']): el.attrib['label']
            for el in enumeration_list.iterfind('xtce:Enumeration', ns)
        }

    def parse_value(self, packet: Packet, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.

        Returns
        -------
        parsed_value : int
            Raw encoded value
        derived_value : str
            Resulting enum label associated with the (usually integer-)encoded data value.
        """
        raw, _ = super().parse_value(packet, **kwargs)
        # Note: The enum lookup only operates on raw values. This is specified in 4.3.2.4.3.6 of the XTCE spec "
        # CCSDS 660.1-G-2
        try:
            label = self.enumeration[raw]
        except KeyError as exc:
            raise ValueError(f"Failed to find raw value {raw} in enum lookup list {self.enumeration}.") from exc
        return raw, label


class BinaryParameterType(ParameterType):
    """<xtce:BinaryParameterType>"""

    def __init__(self, name: str, encoding: BinaryDataEncoding, unit: Optional[str] = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'
        encoding : BinaryDataEncoding
            Must be a BinaryDataEncoding object since binary data can't be encoded other ways.
        unit : Optional[str]
            String describing the unit for the stored value.
        """
        if not isinstance(encoding, BinaryDataEncoding):
            raise ValueError("BinaryParameterType may only be instantiated with a BinaryDataEncoding encoding.")
        super().__init__(name=name, encoding=encoding, unit=unit)
        self.encoding = encoding


class BooleanParameterType(ParameterType):
    """<xtce:BooleanParameterType>"""

    def __init__(self, name: str, encoding: DataEncoding, unit: Optional[str] = None):
        """Constructor that just issues a warning if the encoding is String or Binary"""
        if isinstance(encoding, (BinaryDataEncoding, StringDataEncoding)):
            warnings.warn(f"You are encoding a BooleanParameterType with a {type(encoding)} encoding."
                          f"This is almost certainly a very bad idea because the behavior of string and binary "
                          f"encoded booleans is not specified in XTCE. e.g. is the string \"0\" truthy?")
        super().__init__(name, encoding, unit)

    def parse_value(self, packet: Packet, **kwargs):
        """Using the parameter type definition and associated data encoding, parse a value from a bit stream starting
        at the current cursor position.

        Parameters
        ----------
        packet: Packet
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.


        Returns
        -------
        parsed_value : int
            Raw encoded value
        derived_value : str
            Resulting boolean representation of the encoded raw value
        """
        raw, _ = super().parse_value(packet, **kwargs)
        # Note: This behaves very strangely for String and Binary data encodings.
        # Don't use those for Boolean parameters. The behavior isn't specified well in XTCE.
        return raw, bool(raw)


class TimeParameterType(ParameterType, metaclass=ABCMeta):
    """Abstract class for time parameter types"""

    def __init__(self, name: str, encoding: DataEncoding, unit: Optional[str] = None,
                 epoch: Optional[str] = None, offset_from: Optional[str] = None):
        """Constructor

        Parameters
        ----------
        name : str
            Parameter type name. Usually something like 'MSN__PARAM_Type'.
        encoding : DataEncoding
            How the data is encoded. e.g. IntegerDataEncoding, StringDataEncoding, etc.
        unit : Optional[str]
            String describing the unit for the stored value. Note that if a scale and offset are provided on
            the Encoding element, the unit applies to the scaled value, not the raw value.
        epoch : Optional[str]
            String describing the starting epoch for the date or datetime encoded in the parameter.
            Must be xs:date, xs:dateTime, or one of the following: "TAI", "J2000", "UNIX", "POSIX", "GPS".
        offset_from : Optional[str]
            Used to reference another time parameter by name. It allows
            for the stringing together of several dissimilar but related time parameters.

        Notes
        -----
        The XTCE spec is not very clear about OffsetFrom or what it is for. We parse it but don't use it for
        anything.
        """
        super().__init__(name, encoding, unit=unit)
        self.epoch = epoch
        self.offset_from = offset_from

    @classmethod
    def from_parameter_type_xml_element(cls, element: ElementTree.Element, ns: dict):
        """Create a *TimeParameterType from an <xtce:*TimeParameterType> XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The XML element from which to create the object.
        ns: dict
            XML namespace dict

        Returns
        -------
        : TimeParameterType
        """
        name = element.attrib['name']
        unit = cls.get_units(element, ns)
        encoding = cls.get_data_encoding(element, ns)
        encoding_unit_scaler = cls.get_time_unit_linear_scaler(element, ns)
        if encoding_unit_scaler:
            encoding.default_calibrator = encoding_unit_scaler
        epoch = cls.get_epoch(element, ns)
        offset_from = cls.get_offset_from(element, ns)
        return cls(name, encoding, unit, epoch, offset_from)

    @staticmethod
    def get_units(parameter_type_element: ElementTree.Element, ns: dict) -> Union[str, None]:
        """Finds the units associated with a parameter type element and parsed them to return a unit string.
        We assume only one <xtce:Unit> but this could be extended to support multiple units.
        See section 4.3.2.2.4 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[str, None]
            Unit string or None if no units are defined
        """
        encoding_element = parameter_type_element.find('xtce:Encoding', ns)
        if encoding_element and "units" in encoding_element.attrib:
            units = encoding_element.attrib["units"]
            return units
        # Units are optional so return None if they aren't specified
        return None

    @staticmethod
    def get_time_unit_linear_scaler(
            parameter_type_element: ElementTree.Element, ns: dict) -> Union[PolynomialCalibrator, None]:
        """Finds the linear calibrator associated with the Encoding element for the parameter type element.
        See section 4.3.2.4.8.3 of CCSDS 660.1-G-2

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[PolynomialCalibrator, None]
            The PolynomialCalibrator, or None if we couldn't create a valid calibrator from the XML element
        """
        encoding_element = parameter_type_element.find('xtce:Encoding', ns)
        coefficients = []

        if "offset" in encoding_element.attrib:
            offset = encoding_element.attrib["offset"]
            c0 = PolynomialCoefficient(coefficient=float(offset), exponent=0)
            coefficients.append(c0)

        if "scale" in encoding_element.attrib:
            scale = encoding_element.attrib["scale"]
            c1 = PolynomialCoefficient(coefficient=float(scale), exponent=1)
            coefficients.append(c1)
        # If we have an offset but not a scale, we need to add a first order term with coefficient 1
        elif "offset" in encoding_element.attrib:
            c1 = PolynomialCoefficient(coefficient=1, exponent=1)
            coefficients.append(c1)

        if coefficients:
            return PolynomialCalibrator(coefficients=coefficients)
        # If we didn't find offset nor scale, return None (no calibrator)
        return None

    @staticmethod
    def get_epoch(parameter_type_element: ElementTree.Element, ns: dict) -> Union[str, None]:
        """Finds the epoch associated with a parameter type element and parses them to return an epoch string.
        See section 4.3.2.4.9 of CCSDS 660.1-G-2

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[str, None]
            The epoch string, which may be a datetime string or a named epoch such as TAI. None if the element was
            not found.
        """
        epoch_element = parameter_type_element.find('xtce:ReferenceTime/xtce:Epoch', ns)
        if epoch_element is not None:
            return epoch_element.text
        return None

    @staticmethod
    def get_offset_from(parameter_type_element: ElementTree.Element, ns: dict) -> Union[str, None]:
        """Finds the parameter referenced in OffsetFrom in a parameter type element and returns the name of the
        referenced parameter (which must be of type TimeParameterType).
        See section 4.3.2.4.9 of CCSDS 660.1-G-1

        Parameters
        ----------
        parameter_type_element : ElementTree.Element
            The parameter type element
        ns : dict
            XML namespace dictionary

        Returns
        -------
        : Union[str, None]
            The named of the referenced parameter. None if no OffsetFrom element was found.
        """
        offset_from_element = parameter_type_element.find('xtce:ReferenceTime/xtce:OffsetFrom', ns)
        if offset_from_element is not None:
            return offset_from_element.attrib['parameterRef']
        return None


class AbsoluteTimeParameterType(TimeParameterType):
    """<xtce:AbsoluteTimeParameterType>"""
    pass


class RelativeTimeParameterType(TimeParameterType):
    """<xtce:RelativeTimeParameterType>"""
    pass


class Parseable(Protocol):
    """Defines an object that can be parsed from packet data."""
    def parse(self, packet, **parse_value_kwargs) -> dict:
        """Parse this entry from the packet data and add the necessary items to the parsed_items dictionary."""


@dataclass
class Parameter(Parseable):
    """<xtce:Parameter>

    Parameters
    ----------
    name : str
        Parameter name. Typically something like MSN__PARAMNAME
    parameter_type : ParameterType
        Parameter type object that describes how the parameter is stored.
    short_description : str
        Short description of parameter as parsed from XTCE
    long_description : str
        Long description of parameter as parsed from XTCE
    """
    name: str
    parameter_type: ParameterType
    short_description: Optional[str] = None
    long_description: Optional[str] = None

    def parse(self, packet: Packet, **parse_value_kwargs) -> dict:
        """Parse this parameter from the packet data.

        Create a ``ParsedDataItem`` and add it to the parsed_items dictionary.
        """
        parsed_value, derived_value = self.parameter_type.parse_value(
            packet, **parse_value_kwargs)

        packet.parsed_data[self.name] = ParsedDataItem(
            name=self.name,
            unit=self.parameter_type.unit,
            raw_value=parsed_value,
            derived_value=derived_value,
            short_description=self.short_description,
            long_description=self.long_description
        )
        return packet.parsed_data


@dataclass
class SequenceContainer(Parseable):
    """<xtce:SequenceContainer>

    Parameters
    ----------
    name : str
        Container name
    entry_list : list
        List of Parameter objects
    long_description : str
        Long description of the container
    base_container_name : str
        Name of the base container from which this may inherit if restriction criteria are met.
    restriction_criteria : list
        A list of MatchCriteria elements that evaluate to determine whether the SequenceContainer should
        be included.
    abstract : bool
        True if container has abstract=true attribute. False otherwise.
    inheritors : list, Optional
        List of SequenceContainer objects that may inherit this one's entry list if their restriction criteria
        are met. Any SequenceContainers with this container as base_container_name should be listed here.
    """
    name: str
    entry_list: list  # List of Parameter objects, found by reference
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    base_container_name: Optional[str] = None
    restriction_criteria: Optional[list] = field(default_factory=lambda: [])
    abstract: bool = False
    inheritors: Optional[List['SequenceContainer']] = field(default_factory=lambda: [])

    def __post_init__(self):
        # Handle the explicit None passing for default values
        self.restriction_criteria = self.restriction_criteria or []
        self.inheritors = self.inheritors or []

    def parse(self, packet: Packet, **parse_value_kwargs) -> dict:
        """Parse the entry list of parameters/containers in the order they are expected in the packet.

        This could be recursive if the entry list contains SequenceContainers.
        """
        for entry in self.entry_list:
            packet.parsed_data = entry.parse(packet=packet, **parse_value_kwargs)
        return packet.parsed_data


FlattenedContainer = namedtuple('FlattenedContainer', ['entry_list', 'restrictions'])


class XtcePacketDefinition:
    """Object representation of the XTCE definition of a CCSDS packet object"""

    _tag_to_type_template = {
        '{{{xtce}}}StringParameterType': StringParameterType,
        '{{{xtce}}}IntegerParameterType': IntegerParameterType,
        '{{{xtce}}}FloatParameterType': FloatParameterType,
        '{{{xtce}}}EnumeratedParameterType': EnumeratedParameterType,
        '{{{xtce}}}BinaryParameterType': BinaryParameterType,
        '{{{xtce}}}BooleanParameterType': BooleanParameterType,
        '{{{xtce}}}AbsoluteTimeParameterType': AbsoluteTimeParameterType,
        '{{{xtce}}}RelativeTimeParameterType': RelativeTimeParameterType,
    }

    def __init__(self, xtce_document: TextIO, ns: Optional[dict] = None):
        """Instantiate an object representation of a CCSDS packet definition, according to a format specified in an XTCE
        XML document. The parser iteratively builds sequences of parameters according to the
        SequenceContainers specified in the XML document's ContainerSet element. The notions of container inheritance
        (via BaseContainer) and nested container (by including a SequenceContainer within a SequenceContainer) are
        supported. Exclusion of containers based on topLevelPacket in AncillaryData is not supported, so all
        containers are examined and returned.

        Parameters
        ----------
        xtce_document : TextIO
            Path to XTCE XML document containing packet definition.
        ns : Optional[dict]
            Optional different namespace than the default xtce namespace.
        """
        self._sequence_container_cache = {}  # Lookup for parsed sequence container objects
        self._parameter_cache = {}  # Lookup for parsed parameter objects
        self._parameter_type_cache = {}  # Lookup for parsed parameter type objects
        self.tree = ElementTree.parse(xtce_document)
        self.ns = ns or self.tree.getroot().nsmap
        self.type_tag_to_object = {k.format(**self.ns): v for k, v in
                                   self._tag_to_type_template.items()}

        self._populate_sequence_container_cache()

    def __getitem__(self, item):
        return self._sequence_container_cache[item]

    def _populate_sequence_container_cache(self):
        """Force populating sequence_container_cache by parsing all SequenceContainers"""
        for sequence_container in self.container_set.iterfind('xtce:SequenceContainer', self.ns):
            self._sequence_container_cache[
                sequence_container.attrib['name']
            ] = self.parse_sequence_container_contents(sequence_container)

        # Back-populate the list of inheritors for each container
        for name, sc in self._sequence_container_cache.items():
            if sc.base_container_name:
                self._sequence_container_cache[sc.base_container_name].inheritors.append(name)

    def parse_sequence_container_contents(self, sequence_container: ElementTree.Element) -> SequenceContainer:
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        sequence_container : ElementTree.Element
            The SequenceContainer element to parse.

        Returns
        -------
        : SequenceContainer
            SequenceContainer containing an entry_list of SequenceContainers and Parameters
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters for the current SequenceContainer
        try:
            base_container, restriction_criteria = self._get_container_base_container(sequence_container)
            base_sequence_container = self.parse_sequence_container_contents(base_container)
            base_container_name = base_sequence_container.name
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        container_contents = sequence_container.find('xtce:EntryList', self.ns).findall('*', self.ns)

        for entry in container_contents:
            if entry.tag == '{{{xtce}}}ParameterRefEntry'.format(**self.ns):  # pylint: disable=consider-using-f-string
                parameter_name = entry.attrib['parameterRef']

                # If we've already parsed this parameter in a different container
                if parameter_name in self._parameter_cache:
                    entry_list.append(self._parameter_cache[parameter_name])
                else:
                    parameter_element = self._find_parameter(parameter_name)
                    parameter_type_name = parameter_element.attrib['parameterTypeRef']

                    # If we've already parsed this parameter type for a different parameter
                    if parameter_type_name in self._parameter_type_cache:
                        parameter_type_object = self._parameter_type_cache[parameter_type_name]
                    else:
                        parameter_type_element = self._find_parameter_type(parameter_type_name)
                        try:
                            parameter_type_class = self.type_tag_to_object[parameter_type_element.tag]
                        except KeyError as e:
                            if (
                                    "ArrayParameterType" in parameter_type_element.tag or
                                    "AggregateParameterType" in parameter_type_element.tag
                            ):
                                raise NotImplementedError(f"Unsupported parameter type {parameter_type_element.tag}. "
                                                          "Supporting this parameter type is in the roadmap but has "
                                                          "not yet been implemented.") from e
                            raise InvalidParameterTypeError(f"Invalid parameter type {parameter_type_element.tag}. "
                                                            "If you believe this is a valid XTCE parameter type, "
                                                            "please open a feature request as a Github issue with a "
                                                            "reference to the XTCE element description for the "
                                                            "parameter type element.") from e
                        parameter_type_object = parameter_type_class.from_parameter_type_xml_element(
                            parameter_type_element, self.ns)
                        self._parameter_type_cache[parameter_type_name] = parameter_type_object  # Add to cache

                    parameter_short_description = parameter_element.attrib['shortDescription'] if (
                        'shortDescription' in parameter_element.attrib
                    ) else None
                    parameter_long_description = parameter_element.find('xtce:LongDescription', self.ns).text if (
                        parameter_element.find('xtce:LongDescription', self.ns) is not None
                    ) else None

                    parameter_object = Parameter(
                        name=parameter_name,
                        parameter_type=parameter_type_object,
                        short_description=parameter_short_description,
                        long_description=parameter_long_description
                    )
                    entry_list.append(parameter_object)
                    self._parameter_cache[parameter_name] = parameter_object  # Add to cache
            elif entry.tag == '{{{xtce}}}ContainerRefEntry'.format(  # pylint: disable=consider-using-f-string
                    **self.ns):
                nested_container = self._find_container(name=entry.attrib['containerRef'])
                entry_list.append(self.parse_sequence_container_contents(nested_container))

        short_description = sequence_container.attrib['shortDescription'] if (
            'shortDescription' in sequence_container.attrib
        ) else None
        long_description = sequence_container.find('xtce:LongDescription', self.ns).text if (
            sequence_container.find('xtce:LongDescription', self.ns) is not None
        ) else None

        return SequenceContainer(name=sequence_container.attrib['name'],
                                 entry_list=entry_list,
                                 base_container_name=base_container_name,
                                 restriction_criteria=restriction_criteria,
                                 abstract=self._is_abstract_container(sequence_container),
                                 short_description=short_description,
                                 long_description=long_description)

    @property
    def named_containers(self) -> Dict[str, SequenceContainer]:
        """Property accessor that returns the dict cache of SequenceContainer objects"""
        return self._sequence_container_cache

    @property
    def named_parameters(self) -> Dict[str, Parameter]:
        """Property accessor that returns the dict cache of Parameter objects"""
        return self._parameter_cache

    @property
    def named_parameter_types(self) -> Dict[str, ParameterType]:
        """Property accessor that returns the dict cache of ParameterType objects"""
        return self._parameter_type_cache

    # DEPRECATED! This is only used by CSV-parser code. Remove for 5.0.0 release
    @property
    def flattened_containers(self):
        """Accesses a flattened, generic representation of non-abstract packet definitions along with their
        aggregated inheritance
        restrictions.

        Returns
        -------
        : dict
            A modified form of the _sequence_container_cache, flattened out to eliminate nested sequence containers
            and with all restriction logic aggregated together for easy comparisons.
            {
            "PacketNameA": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            },
            "PacketNameB": {
            FlattenedContainer(
            entry_list=[Parameter, Parameter, ...],
            restrictions={"ParameterName": value, "OtherParamName": value, ...}
            )
            }, ...
            }
        """

        def flatten_container(sequence_container: SequenceContainer):
            """Flattens the representation of a SequenceContainer object into a list of Parameters (in order) and
            an aggregated dictionary of restriction criteria where the keys are Parameter names and the values are the
            required values of those parameters in order to adopt the SequenceContainer's definition.

            Parameters
            ----------
            sequence_container : SequenceContainer
                SequenceContainer object to flatten, recursively.

            Returns
            -------
            : list
                List of Parameters, in order.
            : dict
                Dictionary of required Parameter values in order to use this definition.
            """
            aggregated_entry_list = []
            aggregated_restrictions = []
            for entry in sequence_container.entry_list:
                if isinstance(entry, SequenceContainer):
                    if entry.restriction_criteria:
                        aggregated_restrictions += entry.restriction_criteria
                    entry_list, restrictions = flatten_container(entry)
                    aggregated_entry_list += entry_list
                    aggregated_restrictions += restrictions
                elif isinstance(entry, Parameter):
                    aggregated_entry_list.append(entry)
            return aggregated_entry_list, aggregated_restrictions

        warnings.warn("The 'flattened_containers' property is deprecated to allow for dynamic container "
                      "inheritance matching during parsing.", DeprecationWarning)
        return {
            name: FlattenedContainer(*flatten_container(sc))
            for name, sc in self._sequence_container_cache.items()
            if not sc.abstract
        }

    @property
    def container_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ContainerSet> element, containing all the sequence container elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ContainerSet', self.ns)

    @property
    def parameter_type_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterTypeSet> element, containing all parameter type elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterTypeSet', self.ns)

    @property
    def parameter_set(self) -> ElementTree.Element:
        """Property that returns the <xtce:ParameterSet> element, containing all parameter elements."""
        return self.tree.getroot().find('xtce:TelemetryMetaData/xtce:ParameterSet', self.ns)

    @staticmethod
    def _is_abstract_container(container_element: ElementTree.Element) -> bool:
        """Determine in a SequenceContainer element is abstract

        Parameters
        ----------
        container_element : ElementTree.Element
            SequenceContainer element to examine

        Returns
        -------
        : bool
            True if SequenceContainer element has the attribute abstract=true. False otherwise.
        """
        if 'abstract' in container_element.attrib:
            return container_element.attrib['abstract'].lower() == 'true'
        return False

    def _find_container(self, name: str) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        matches = self.container_set.findall(f"./xtce:SequenceContainer[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching container_set with name {name}. " \
                                  f"Container names are expected to exist and be unique."
        return matches[0]

    def _find_parameter(self, name: str) -> ElementTree.Element:
        """Finds an XTCE Parameter in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter to find

        Returns
        -------
        : ElementTree.Element
        """
        matches = self.parameter_set.findall(f"./xtce:Parameter[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching parameters with name {name}. " \
                                  f"Parameter names are expected to exist and be unique."
        return matches[0]

    def _find_parameter_type(self, name: str) -> ElementTree.Element:
        """Finds an XTCE ParameterType in the tree.

        Parameters
        ----------
        name : str
            Name of the parameter type to find

        Returns
        -------
        : ElementTree.Element
        """
        matches = self.parameter_type_set.findall(f"./*[@name='{name}']", self.ns)
        assert len(matches) == 1, f"Found {len(matches)} matching parameter types with name {name}. " \
                                  f"Parameter type names are expected to exist and be unique."
        return matches[0]

    def _get_container_base_container(
            self,
            container_element: ElementTree.Element) -> Tuple[ElementTree.Element, List[MatchCriteria]]:
        """Examines the container_element and returns information about its inheritance.

        Parameters
        ----------
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : ElementTree.Element
            The base container element of the input container_element.
        : list
            The restriction criteria for the inheritance.
        """
        base_container_element = container_element.find('xtce:BaseContainer', self.ns)
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element.")

        restriction_criteria_element = base_container_element.find('xtce:RestrictionCriteria', self.ns)
        if restriction_criteria_element is not None:
            comparison_list_element = restriction_criteria_element.find('xtce:ComparisonList', self.ns)
            single_comparison_element = restriction_criteria_element.find('xtce:Comparison', self.ns)
            boolean_expression_element = restriction_criteria_element.find('xtce:BooleanExpression', self.ns)
            custom_algorithm_element = restriction_criteria_element.find('xtce:CustomAlgorithm', self.ns)
            if custom_algorithm_element is not None:
                raise NotImplementedError("Detected a CustomAlgorithm in a RestrictionCriteria element. "
                                          "This is not implemented.")

            if comparison_list_element is not None:
                comparisons = comparison_list_element.findall('xtce:Comparison', self.ns)
                restrictions = [Comparison.from_match_criteria_xml_element(comp, self.ns) for comp in comparisons]
            elif single_comparison_element is not None:
                restrictions = [Comparison.from_match_criteria_xml_element(single_comparison_element, self.ns)]
            elif boolean_expression_element is not None:
                restrictions = [BooleanExpression.from_match_criteria_xml_element(boolean_expression_element, self.ns)]
            else:
                raise ValueError("Detected a RestrictionCriteria element containing no "
                                 "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm.")
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return self._find_container(base_container_element.attrib['containerRef']), restrictions


def _extract_bits(data: bytes, start_bit: int, nbits: int):
    """Extract nbits from the data starting from the least significant end.

    If data = 00110101 11001010, start_bit = 2, nbits = 9, then the bits extracted are "110101110".
    Those bits are turned into a Python integer and returned.

    Parameters
    ----------
    data : bytes
        Data to extract bits from
    start_bit : int
        Starting bit location within the data
    nbits : int
        Number of bits to extract

    Returns
    -------
    int
        Extracted bits as an integer
    """
    # Get the bits from the packet data
    # Select the bytes that contain the bits we want.
    start_byte = start_bit // 8  # Byte index containing the start_bit
    start_bit_within_byte = start_bit % 8  # Bit index within the start_byte
    end_byte = start_byte + (start_bit_within_byte + nbits + 7) // 8
    data = data[start_byte:end_byte]  # Chunk of bytes containing the data item we want to parse
    # Convert the bytes to an integer for bitwise operations
    value = int.from_bytes(data, byteorder="big")
    if start_bit_within_byte == 0 and nbits % 8 == 0:
        # If we're extracting whole bytes starting at a byte boundary, we don't need any bitshifting
        # This is faster, especially for large binary chunks
        return value

    # Shift the value to the right to move the LSB of the data item we want to parse
    # to the least significant position, then mask out the number of bits we want to keep
    return (value >> (len(data) * 8 - start_bit_within_byte - nbits)) & (2 ** nbits - 1)
