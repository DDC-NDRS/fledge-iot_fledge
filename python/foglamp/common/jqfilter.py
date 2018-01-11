# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

""" A simple implementation using the jq product to apply a transformation to the JSON document
"""

import pyjq

from foglamp.common import logger

__author__ = "Vaibhav Singhal"
__copyright__ = "Copyright (c) 2017 OSI Soft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


class JQFilter:
    """JQFilter class to use the jq product.
    jq is a lightweight and flexible JSON processor.
    This class uses pyjq (https://pypi.python.org/pypi/jq) which contains Python bindings for jq
    """

    def __init__(self):
        """Initialise the JQFilter"""
        super().__init__()
        self._logger = logger.setup("JQFilter")

    def transform(self, apply_filter, reading_block, filter_string):
        """
        Args:
            apply_filter: Flag to tell whether to apply filter or not,
                if flag is false then reading_block is returned as is.
            reading_block: Formatted JSON on which filter needs to be applied.
            filter_string: filter to apply. Filter should be in JQ format.
        Returns: transformed JSON (if apply_filter is true)
        Raises:
            TypeError: If reading_block is not a valid JSON
            ValueError: If filter is not a proper JQ filter
        Examples:
            Refer https://stedolan.github.io/jq/tutorial/ for basic JQ filter examples
            Refer test_jq_filter.py for positive and negative scenarios
                and usage with plugins using defined configurations.

        """
        if apply_filter.upper() == "FALSE":
            return reading_block
        try:
            return pyjq.all(filter_string, reading_block)
        except TypeError as ex:
            self._logger.error("Invalid JSON passed, exception %s", str(ex))
            raise
        except ValueError as ex:
            self._logger.error("Failed to transform, please check the transformation rule, exception %s", str(ex))
            raise
