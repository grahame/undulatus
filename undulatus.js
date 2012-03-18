{
  "_id" : "_design/undulatus",
  "revision" : "1",
  "views" : {
    "replies" : {
      "map" : "function(doc) { emit(doc.in_reply_to_status_id_str, doc._id) }"
    }
  }
}
