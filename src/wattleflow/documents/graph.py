# Module Name: documents/graph.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains GraphDocument class.

from os import path
from datetime import datetime
from rdflib import Graph, URIRef, Literal
from wattleflow.concrete.document import Document


class GraphDocument(Document[Graph]):
    def __init__(self, uri: str = None):
        """
        Initializes an RDF graph document.
        If a filename is provided, it attempts to load the graph from the file.
        """
        super().__init__()
        self._data = Graph()
        self._uri = uri
        self._lastchange = datetime.now()

    @property
    def graph(self) -> Graph:
        return self._data

    @property
    def uri(self) -> str:
        return self._uri

    def add_triple(self, subject: str, predicate: str, obj: str):
        self._data.add((URIRef(subject), URIRef(predicate), Literal(obj)))
        self._lastchange = datetime.now()

    def remove_triple(self, subject: str, predicate: str, obj: str):
        self._data.remove((URIRef(subject), URIRef(predicate), Literal(obj)))
        self._lastchange = datetime.now()

    def query_graph(self, sparql_query: str):
        return self._data.query(sparql_query)

    def save_graph(self, format="turtle"):
        if not self._filename:
            raise ValueError("No filename specified for saving the graph.")

        self._data.serialize(destination=self._filename, format=format)
        self._lastchange = datetime.now()

    def load_graph(self, format="turtle"):
        if not path.exists(self._filename):
            raise FileNotFoundError(f"File not found: {self._filename}")

        self._data.parse(self._filename, format=format)
        self._lastchange = datetime.now()

    def update_content(self, new_graph: Graph):
        if not isinstance(new_graph, Graph):
            raise TypeError(f"Expected rdflib.Graph, got {type(new_graph)}")
        self._data = new_graph
        self._lastchange = datetime.now()

    def get_triples(self):
        return list(self._data)

    def clear_graph(self):
        self._data.remove((None, None, None))
        self._lastchange = datetime.now()
