{
  "_id" : "_design/undulatus",
  "revision" : "7",
  "views" : {
    "replies" : {
      "map" : "function(doc) { if (doc.in_reply_to_status_id_str) { emit(doc.in_reply_to_status_id_str, null); } }"
    },
    "byuser" : {
        "map" : "function(doc) { if (doc.user && doc.user.screen_name) { emit([doc.user.screen_name, doc.id], null); } }"
    },
    "byid" : {
        "map" : "function(doc) { if (doc.id) { emit(doc.id, null); } }"
    }
  }
}
