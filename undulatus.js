{
  "_id" : "_design/undulatus",
  "revision" : "2",
  "views" : {
    "replies" : {
      "map" : "function(doc) { emit(doc.in_reply_to_status_id_str, null); }"
    },
    "byuser" : {
        "map" : "function(doc) { emit([doc.user.screen_name, doc.id], null); }"
    },
    "byid" : {
        "map" : "function(doc) { emit([doc.id], null); }"
    }
  }
}
