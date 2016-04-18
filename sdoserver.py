#!/usr/bin/env python

# since rdflib uses multiprocessing, monkey shouldn't patch
from gevent import monkey;
old_patchall = monkey.patch_all
monkey.patch_all = lambda : None # try old_patchall(socket=False, threading=False) later

import os
import glob
import rdflib
import unittest
from StringIO import StringIO
from rdflib.plugins.sparql import prepareQuery
from funcserver import Server, make_handler, BaseHandler

make_term = lambda x: rdflib.term.URIRef(x) if isinstance(x, basestring) else x

HTTPSS = "http://"
LHTTPSS = len(HTTPSS)

class RDFApi(object):
    EXT_TO_FORMAT = {
        ".rdfa": "rdfa",
        ".jsonld": "json-ld",
    }
    RDFS = "http://www.w3.org/2000/01/rdf-schema#"
    DOMAIN_INCLUDES = make_term("http://schema.org/domainIncludes")
    RANGE_INCLUDES = make_term("http://schema.org/rangeIncludes")

    def __init__(self, log):
        # the directory where all rdf files are
        self.log = log
        self.files = set()
        self.graph = RDFApi.new_graph()
        self.prepare_queries()

    @classmethod
    def new_graph(cls):
        return rdflib.Graph()

    def add_file(self, fname):
        """ add a file to the graph """
        self.log.debug("attempting to add file %s", fname)
        if fname in self.files:
            self.log.warning("file %s already added, not adding again...", fname)
            return

        name, ext = os.path.splitext(fname)
        fmt = RDFApi.EXT_TO_FORMAT.get(ext)
        if fmt is None:
            raise Exception("Unsupported ext %s for %s" % (ext, fname))

        self.log.debug("loading into graph file=%s", fname)
        self.graph.load(fname, format=fmt)
        self.log.debug("done loading file=%s", fname)
        self.files.add(fname)

    def add_prepared_query(self, name, query, initNs=None):
        self.log.debug("adding prepared query with name %s", name)
        pq = lambda x,y: prepareQuery(x, initNs=y)
        if initNs is None:
            pq = lambda x,y: prepareQuery(x)

        prepared_query = pq(query, initNs)
        self.prepared_queries[name] = (query, prepared_query)
        self.prepared_query_to_str[prepared_query] = query

        return self.prepared_queries[name][-1]

    def prepare_queries(self):
        """ prepares most queries that will be reused """
        self.log.info("preparing queries ...")
        self.prepared_queries = {}
        self.prepared_query_to_str = {}
        initNs = {"rdfs": RDFApi.RDFS}
        get_classes = '''
        SELECT ?class
        WHERE {
            ?class rdf:type rdfs:Class .
        }
        '''
        self.add_prepared_query("get_classes", get_classes, initNs)

        get_properties = '''
        SELECT ?property
        WHERE {
            ?property rdf:type rdf:Property .
        }
        '''
        self.add_prepared_query("get_properties", get_properties, None)

        get_term_to_label = '''
        SELECT ?term ?label
        WHERE {
            ?term rdfs:label ?label
        }
        '''
        self.add_prepared_query("get_term_to_label", get_term_to_label, initNs)

        get_term_to_desc = '''
        SELECT ?term ?desc
        WHERE {
            ?term rdfs:comment ?desc
        }
        '''
        self.add_prepared_query("get_term_to_desc", get_term_to_desc, initNs)

        get_ancestors = '''
        SELECT ?class
        WHERE {
            ?subject rdfs:subClassOf* ?mid .
            ?mid rdfs:subClassOf* ?class .
        }
        group by ?class
        order by count(?mid)
        '''
        self.add_prepared_query("get_ancestors", get_ancestors, initNs)

    def get_desc(self, term):
        term = make_term(term)

        desc = self.term_to_desc.get(term, None)
        if desc is None:
            desc = term.toPython()

        return desc

    def get_id(self, term):
        term = make_term(term)

        if term not in self.classes and term not in self.properties:
            return term.toPython() # not something we know about

        termstr = term.toPython()
        if termstr.startswith(HTTPSS):
            termstr = termstr[LHTTPSS:]

        termstr = '/schema/%s' % termstr
        return termstr

    def get_term_from_str(self, termstr):
        return make_term(termstr)

    def get_label(self, term):
        term = make_term(term)

        label = self.term_to_label.get(term, None)
        if label is None:
            label = term.toPython()

        return label

    def is_term(self, term):
        return isinstance(term, rdflib.term.URIRef)

    def is_known_term(self, term):
        return (term in self.classes or term in self.properties)

    def is_literal(self, term):
        return isinstance(term, rdflib.term.Literal)

    def is_class(self, term):
        term = make_term(term)

        return term in self.classes

    def is_property(self, term):
        term = make_term(term)

        return term in self.properties

    def reload_term_meta(self):
        """ loads a mapping of classes, properties, labels and descriptions
        """
        result = self.execute_prepared_query("get_classes")
        self.classes = set([row[0] for row in result])

        result = self.execute_prepared_query("get_properties")
        self.properties = set([row[0] for row in result])

        result = self.execute_prepared_query("get_term_to_label")
        self.term_to_label = { row[0]: row[1].toPython() for row in result }

        result = self.execute_prepared_query("get_term_to_desc")
        self.term_to_desc = { row[0]: row[1].toPython() for row in result }

    def execute_prepared_query(self, name, **kwargs):
        # log query and ...
        qstr, pq = self.prepared_queries.get(name, (None, None))
        if qstr is None and pq is None:
            raise Exception("could not find query for name %s" % name)


        self.log.debug("executing query: %s", qstr)
        return self.graph.query(pq, **kwargs)

    def get_descendants(self, subject):
        subject = make_term(subject)
        # TODO make this a compiled query

        query = '''
        select ?class where {
            ?class rdfs:subClassOf <%(subject_uri)s> .
        }
        ''' % dict(subject_uri=subject.toPython())

        descendants = [ term[0] for term in
            self.graph.query(query, initNs={"rdfs": RDFApi.RDFS})
        ]
        return descendants

    def get_ancestors(self, subject):
        subject = make_term(subject)

        # TODO make this a compiled query
        ancestor_query = '''
        select ?class where {
            <%(subject_uri)s> rdfs:subClassOf* ?mid .
            ?mid rdfs:subClassOf* ?class .
        }
        group by ?class
        order by count(?mid)
        ''' % dict(subject_uri=subject.toPython())
        ancestors = [
            term[0] for term in
            self.graph.query(ancestor_query, initNs={"rdfs": RDFApi.RDFS})
        ]
        return ancestors

    def get_ancestors_beta(self, subject):
        subject = make_term(subject)

        query, prepared_query = self.prepared_queries["get_ancestors"]
        result = self.execute_prepared_query(
            "get_ancestors", initBindings={"subject": subject}
        )
        ancestors = [ term[0] for term in result ]
        return ancestors

    def get_properties_for_class_as_domain(self, class_resource):
        class_resource = make_term(class_resource)

        # TODO does it have to be OPTIONAL rangeIncludes ?
        # TODO what about domain and range itself
        # TODO make this prepared query
        query = '''
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?property ?object
        WHERE {
            ?property <http://schema.org/domainIncludes> <%(subject_uri)s> .
            ?property <http://schema.org/rangeIncludes> ?object .
        }
        ORDER BY ?property
        ''' % dict(subject_uri=class_resource.toPython())

        property_to_obj_list = {}
        result = self.graph.query(query)
        for prop, target in result:
            property_to_obj_list.setdefault(prop, []).append(target)

        return property_to_obj_list

    def get_properties_for_class_as_range(self, class_resource):
        # TODO make this prepared query
        class_resource = make_term(class_resource)
        query = '''
        prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?property ?object
        WHERE {
            ?property <http://schema.org/rangeIncludes> <%(subject_uri)s> .
            ?property <http://schema.org/domainIncludes> ?object .
        }
        ORDER BY ?property
        ''' % dict(subject_uri=class_resource.toPython())

        property_to_obj_list = {}
        result = self.graph.query(query)
        for prop, target in result:
            property_to_obj_list.setdefault(prop, []).append(target)

        return property_to_obj_list

    def is_predicate_domain_includes(self, predicate):
        predicate = make_term(predicate)
        return predicate == RDFApi.DOMAIN_INCLUDES

    def is_predicate_range_includes(self, predicate):
        predicate = make_term(predicate)
        return predicate == RDFApi.RANGE_INCLUDES

    def get_predicate_object_for_subject(self, subject):
        # TODO make this prepared query
        subject = make_term(subject)

        query = '''
        SELECT ?predicate ?object
        WHERE {
            <%(subject_uri)s> ?predicate ?object
        }
        ORDER BY ?predicate
        ''' % dict(subject_uri=subject.toPython())
        result = self.graph.query(query)
        return [ (row[0], row[1]) for row in self.graph.query(query) ]

class SdoServer(Server):
    NAME = 'SDOServer'
    DESC = """Load rdf graphs and explore them interactively.
    Special logic to handle schema.org domainIncludes and rangeIncludes.
    """

    def run_tests(self, rdf_dirs):
        from tests.test_consistency import GraphConsistenctyTestCase
        self.log.info("running tests...")
        self.log.info("=" * 100)
        os.environ["RDF_DIR"] = ':'.join(rdf_dirs)
        stream = StringIO()
        runner = unittest.TextTestRunner(stream=stream)
        result = runner.run(unittest.makeSuite(GraphConsistenctyTestCase))

        self.log.info("tests run: %s", result.testsRun)
        self.log.info("errors: %s", result.errors)
        self.log.info("failures: %s", result.failures)
        stream.seek(0)
        self.log.info("output: %s", stream.read())

        if len(result.failures) > 0:
            self.log.error("tests are failing !!!")

        self.log.info("=" * 100)

    def prepare_api(self):
        rdf_dirs = map(os.path.abspath, self.args.rdf_dirs)
        # before preparing api, make sure tests pass !
        # TODO remove this , and do it externally ?
        if not self.args.skip_tests:
            self.run_tests(rdf_dirs)

        filelist = []
        for rdf_dir in rdf_dirs:
            for ext in RDFApi.EXT_TO_FORMAT.iterkeys():
                files = glob.glob(os.path.join(rdf_dir, '*%s' % ext))
                filelist.extend(files)

        api = RDFApi(self.log)
        for f in filelist:
            api.add_file(f)

        api.reload_term_meta()
        self.log.info("api is ready to be used...")
        return api

    def prepare_nav_tabs(self, nav_tabs):
        nav_tabs.append(('TreeSchema', '/schema/tree'))
        nav_tabs.append(('FullSchema', '/schema/full'))
        nav_tabs.append(('Schema', '/schema/schema.org/Thing'))

        return nav_tabs

    def prepare_handlers(self):
        return [
            (r'/schema/tree', make_handler('tree_schema_tab.html', BaseHandler)),
            (r'/schema/full', make_handler('full_schema_tab.html', BaseHandler)),
            # (r'/schema/(\w+)', make_handler('indivdual.html', BaseHandler)),
            (r'/schema/.*', make_handler('single_schema_tab.html', BaseHandler)),
        ]

    def prepare_template_loader(self, loader):
        loader.add_dir('./templates')
        return loader

    def define_args(self, parser):
        parser.add_argument("rdf_dirs", nargs="+", help="Directory containing rdf files")
        parser.add_argument("--skip-tests", default=False, action="store_true",
            help="skips initial test check when starting server...",
        )

if __name__ == '__main__':
    # run tests before starting...
    SdoServer().run()
