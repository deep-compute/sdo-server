# Schema Dot Org Server

Schema.org offers a well thought out RDF schema for representing knowledge. It serves as a good starting point for modelling application specific ontologies. While Schema.org supports the notion of "Extensions", we needed more flexibility in order to iterate rapidly.

`SDOServer` offers the ability to support a development cycle for RDF Schemas based on Schema.org Ontology. It lets you view and explore your RDF Schema interactively in a browser and does some basic validation.

The RDF files provided as input to `SDOServer` follow the same format as those of schema.org. The views are rendered based on `rangeIncludes` and `domainIncludes` both of which are RDFS properties defined by schema.org.

## Installation and Usage

```
git clone https://github.com/deep-compute/sdo-server.git && cd sdo-server
pip install git+git://github.com/deep-compute/basescript.git
pip install git+git://github.com/deep-compute/funcserver.git
pip install -r requirements.txt
# <RDFDIRN> is a directory where rdfs files are stored
python sdoserver.py --log-level info --port <PORT> <RDFDIR1> <RDFDIR2>
```

## Misc notes

`SDOServer` is built using [funcserver][1].

[1]: https://github.com/deep-compute/funcserver.git
