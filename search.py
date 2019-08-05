#!/usr/bin/env python

import os
import whoosh.fields
import whoosh.qparser
import whoosh.index


class RDFSearch(object):
    """ creates a whoosh index on a graph """

    def __init__(self, index_dir, graph=None):
        self.index_dir = index_dir
        self.schema = whoosh.fields.Schema(
            uri=whoosh.fields.ID(stored=True), body=whoosh.fields.TEXT
        )

        self.index = None
        if os.path.exists(self.index_dir):
            self.index = whoosh.index.open_dir(self.index_dir)

        if self.index is None:
            os.makedirs(self.index_dir)
            self.index = whoosh.index.create_in(self.index_dir, self.schema)

        if graph is not None:
            self.index_graph(graph)

        self.searcher = self.index.searcher()
        self.term_parser = whoosh.qparser.MultifieldParser(
            ["uri", "body"], schema=self.schema, group=whoosh.qparser.OrGroup
        )

    def index_graph(self, graph):
        """ takes a graph to be indexed """
        writer = self.index.writer()
        for (s, p, o) in graph.triples((None, None, None)):
            uri = "%s" % s
            body = "%s" % o
            writer.add_document(uri=uri, body=body)

        writer.commit()

    def search(self, term):
        results = self.searcher.search(self.term_parser.parse(term))
        return [r["uri"] for r in results]

    def close(self):
        self.searcher.close()
