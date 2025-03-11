# Module Name: documents/graph.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains GraphDocument class.

from os import path
from datetime import datetime
from rdflib import Graph, URIRef, Literal  # Namespace
from wattleflow.concrete.document import Document

# from rdflib.namespace import RDF, RDFS, FOAF


class GraphDocument(Document[Graph]):
    def __init__(self, filename: str = None):
        """
        Initializes an RDF graph document.
        If a filename is provided, it attempts to load the graph from the file.
        """
        super().__init__()
        self._graph = Graph()
        self._filename = filename
        self._lastchange = datetime.now()

        if filename and path.exists(filename):
            self.load_graph()

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def filename(self) -> str:
        return self._filename

    def add_triple(self, subject: str, predicate: str, obj: str):
        self._graph.add((URIRef(subject), URIRef(predicate), Literal(obj)))
        self._lastchange = datetime.now()

    def remove_triple(self, subject: str, predicate: str, obj: str):
        self._graph.remove((URIRef(subject), URIRef(predicate), Literal(obj)))
        self._lastchange = datetime.now()

    def query_graph(self, sparql_query: str):
        return self._graph.query(sparql_query)

    def save_graph(self, format="turtle"):
        if not self._filename:
            raise ValueError("No filename specified for saving the graph.")

        self._graph.serialize(destination=self._filename, format=format)
        self._lastchange = datetime.now()

    def load_graph(self, format="turtle"):
        if not path.exists(self._filename):
            raise FileNotFoundError(f"File not found: {self._filename}")

        self._graph.parse(self._filename, format=format)
        self._lastchange = datetime.now()

    def update_content(self, new_graph: Graph):
        if not isinstance(new_graph, Graph):
            raise TypeError(f"Expected rdflib.Graph, got {type(new_graph)}")
        self._graph = new_graph
        self._lastchange = datetime.now()

    def get_triples(self):
        return list(self._graph)

    def clear_graph(self):
        self._graph.remove((None, None, None))
        self._lastchange = datetime.now()
