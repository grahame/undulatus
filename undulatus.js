{
  "_id" : "_design/undulatus",
  "revision" : "6",
  "views" : {
    "replies" : {
      "map" : "function(doc) { if (doc.in_reply_to_status_id_str) { emit(doc.in_reply_to_status_id_str, null); } }"
    },
    "byuser" : {
        "map" : "function(doc) { if (doc.user && doc.user.screen_name) { emit([doc.user.screen_name, doc.id], null); } }"
    },
    "byid" : {
        "map" : "function(doc) { if (doc.id) { emit(doc.id, null); } }"
    },
    "byhashtag" : {
        "map" : "function(doc) { var match = function(s) { var r = /(^|\\s)#([^\\s]+)/; var match; while (match = s.match(r)) { s = s.substr(match.index + match[0].length); var hashtag = match[2]; emit(hashtag, null); } }; if (doc['text']) { match(doc['text']); } }"
    }
  }
}
