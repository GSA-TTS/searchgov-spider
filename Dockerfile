FROM docker.elastic.co/elasticsearch/elasticsearch:7.17.20
RUN elasticsearch-plugin install analysis-kuromoji
RUN elasticsearch-plugin install analysis-icu
RUN elasticsearch-plugin install analysis-smartcn
