# sdo-server
A [funcserver][1] to view and explore rdfs files interactively.  
The rdfs files follow the format of schema.org, and views are rendered
based on `rangeIncludes` and `domainIncludes` properties.

## Installation and Usage

```
git clone https://github.com/deep-compute/sdo-server.git && cd sdo-server
pip install git+git://github.com/deep-compute/basescript.git
pip install git+git://github.com/deep-compute/funcserver.git
pip install -r requirements.txt
# <RDFDIRN> is a directory where rdfs files are stored
python sdoserver.py --log-level info --port <PORT> <RDFDIR1> <RDFDIR2>
```

[1]: github.com/deep-compute/funcserver.git
