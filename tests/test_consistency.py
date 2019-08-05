#!/usr/bin/env python

"""
Re-Using SPARQL queries from schema.org and adding more
for ontology consistency.
"""

# TODO use a reasoner !

import os
import sys
import glob
import logging
import unittest
from sdoserver import RDFApi

logging.basicConfig(stream=sys.stderr)
log = logging.getLogger()
warnings = []


class GraphConsistenctyTestCase(unittest.TestCase):
    def setUp(self):
        self.api = RDFApi(log)
        self.rdf_dir = os.getenv("RDF_DIR")
        if self.rdf_dir is None:
            warnings.append("skipping test as RDF_DIR is not set")
            log.warning("skipping test as RDF_DIR is not set")
            raise unittest.SkipTest("Environmental variable RDF_DIR  needs to be set")

        rdf_dirs = self.rdf_dir.split(":")
        filelist = []
        for rdf_dir in rdf_dirs:
            for ext in RDFApi.EXT_TO_FORMAT.iterkeys():
                files = glob.glob(os.path.join(rdf_dir, "*%s" % ext))
                filelist.extend(files)

        for f in filelist:
            self.api.add_file(f)

    def test_even_number_inverseOf(self):
        inverseOf_results = self.api.graph.query(
            """
            SELECT ?x ?y WHERE { ?x <http://schema.org/inverseOf> ?y }
        """
        )
        self.assertEqual(
            len(inverseOf_results) % 2 == 0,
            True,
            "Even number of inverseOf triples expected. Found: %s"
            % len(inverseOf_results),
        )

    # @unittest.expectedFailure # autos
    def test_needless_domainIncludes(self):
        global warnings
        # check immediate subtypes don't declare same domainIncludes
        # TODO: could we use property paths here to be more thorough?
        # rdfs:subClassOf+ should work but seems not to.
        query = """
            prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?prop ?c1 ?c2
            WHERE {
                ?prop <http://schema.org/domainIncludes> ?c1 .
                ?prop <http://schema.org/domainIncludes> ?c2 .
                ?c1 rdfs:subClassOf ?c2 .
                FILTER (?c1 != ?c2) .
            }
            ORDER BY ?prop
        """

        result = self.api.graph.query(query)
        fmt = "property {prop} defining domain, {c1}, [which is subclassOf] {c2} unnecessarily."

        if len(result) > 0:
            for row in result:
                warn = fmt.format(prop=row[0], c1=row[1], c2=row[2])
                warnings.append(warn)
                log.warn(warn)

        self.assertEqual(
            len(result),
            0,
            "No subtype need redeclare a domainIncludes of its parents. Found: %s "
            % len(result),
        )

    # @unittest.expectedFailure
    def test_needlessRangeIncludes(self):
        global warnings
        # as above, but for range. We excuse URL as it is special, not best seen as a Text subtype.
        # check immediate subtypes don't declare same domainIncludes
        # TODO: could we use property paths here to be more thorough?
        query = """
            prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?prop ?c1 ?c2
            WHERE {
                ?prop <http://schema.org/rangeIncludes> ?c1 .
                ?prop <http://schema.org/rangeIncludes> ?c2 .
                ?c1 rdfs:subClassOf ?c2 .
                FILTER (?c1 != ?c2) .
                FILTER (?c1 != <http://schema.org/URL>) .
            }
            ORDER BY ?prop
        """

        result = self.api.graph.query(query)
        fmt = "property {prop} defining range, {c1}, [which is subclassOf] {c2} unnecessarily."

        if len(result) > 0:
            for row in result:
                warn = fmt.format(prop=row[0], c1=row[1], c2=row[2])
                warnings.append(warn)
                log.warn(warn)

        self.assertEqual(
            len(result),
            0,
            "No subtype need redeclare a rangeIncludes of its parents. Found: %s "
            % len(result),
        )

    def test_valid_rangeIncludes(self):
        """ Every range includes should be a valid type """
        query = """
            prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?prop ?c1
            WHERE {
                ?prop <http://schema.org/rangeIncludes> ?c1 .
                OPTIONAL {
                    ?c1 rdf:type ?c2 .
                    ?c1 rdf:type rdfs:Class .
                }.
                FILTER (!BOUND(?c2))
            }
            ORDER BY ?prop
        """

        result = self.api.graph.query(query)
        for row in result:
            log.warn(
                "Property %s invalid rangeIncludes value: %s", row["prop"], row["c1"]
            )

        self.assertEqual(
            len(result),
            0,
            "RangeIncludes should define valid type. Found: %s" % len(result),
        )

    def test_valid_domainIncludes(self):
        """ Every domain includes should be a valid type """
        query = """
            prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?prop ?c1
            WHERE {
                ?prop <http://schema.org/domainIncludes> ?c1 .
                OPTIONAL {
                    ?c1 rdf:type ?c2 .
                    ?c1 rdf:type rdfs:Class .
                }.
                FILTER (!BOUND(?c2))
            }
            ORDER BY ?prop
        """

        result = self.api.graph.query(query)
        for row in result:
            log.warn(
                "Property %s invalid domainIncludes value: %s", row["prop"], row["c1"]
            )

        self.assertEqual(
            len(result),
            0,
            "DomainIncludes should define valid type. Found %s" % len(result),
        )


def tearDownModule():
    global warnings
    if len(warnings) > 0:
        log.warning("%d warnings", len(warnings))
    for warn in warnings:
        log.warning(warn)


# TODO: Unwritten tests (from basics; easier here?)
#
# * different terms should not have identical comments
# * rdflib and internal parsers should have same number of triples
# * if x and y are inverseOf each other, the rangeIncludes types on x should be domainIncludes on y, and vice-versa.
# * need a few supporting functions e.g. all terms, all types, all properties, all enum values; candidates for api later but just use here first.


if __name__ == "__main__":
    unittest.main()
