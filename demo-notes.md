Query 1: Kauffman — retrieval works because top chunks are from 07_reddit_kauffman_csci2021.txt.

Query 2: Joosten — retrieval works because top chunks are from 06_reddit_joosten_csci2011.txt.

Query 3: Moen vs Van Wyk — retrieval works because top chunks are from 10_reddit_csci2041_moen_vanwyk.txt.

Out-of-scope query: pizza near campus — system correctly refuses because the corpus only covers CS professors/courses.

Failure case: original CSCI2041 query was too abstract, so retrieval initially returned a broader recommendation thread instead of the dedicated Moen vs Van Wyk thread.