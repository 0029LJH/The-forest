# 基于官方镜像构建，内置 IK 中文分词插件
# 插件版本与 ES 版本严格一致（8.15.0）
FROM docker.elastic.co/elasticsearch/elasticsearch:8.15.0

RUN bin/elasticsearch-plugin install --batch https://get.infini.cloud/elasticsearch/analysis-ik/8.15.0
