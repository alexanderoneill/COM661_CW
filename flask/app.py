# --------------------------------- IMPORTS -----------------------------------

from typing import ByteString
from flask import Flask, jsonify, make_response, request
from pymongo import MongoClient
from bson import ObjectId
from functools import wraps

import jwt
import datetime
import string

# ------------------------------- ENVIRONMENT ---------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = "mysecret"

client = MongoClient("mongodb://127.0.0.1:27017")
db = client.bizDB
businesses = db.biz

def jwt_required(func):
	@wraps(func)
	def jwt_required_wrapper(*args, **kwargs):
		token = None
		if "x-access-token" in request.headers:
			token = request.headers["x-access-token"]
		if not token:
			return jsonify({"message" : "Token is missing"}), 401
		try:
			data = jwt.decode(token, app.config["SECRET_KEY"])
		except:
			return jsonify({"message" : "Token is invalid"}), 401
		return func(*args, **kwargs)

	return jwt_required_wrapper

# ------------------------------ AUTHENTICATION -------------------------------

@app.route("/api/v1.0/login", methods = ["GET"])
def login():
	auth = request.authorization
	if auth and auth.password == "password":
		token = jwt.encode({"user" : auth.username, "exp" : datetime.datetime.utcnow() + datetime.timedelta(minutes = 30)}, app.config["SECRET_KEY"])
		return jsonify({"token" : token.decode("UTF-8")})

	return make_response("Could not verify", 401, {"WWW-Authenticate" : "Basic realm = 'Login required'"})

# -------------------------------- VALIDATION ---------------------------------                                  

def validateBusinessDetails(name, town, rating):
	namevalid = False
	townvalid = False
	ratingvalid = False
	if len(name) > 0 and name.isalpha() and len(name) < 80:
		namevalid = True
	if len(town) > 0 and town.isalpha() and len(town) < 80:
		townvalid = True
	if len(rating) > 0 and int(rating) > 0 and int(rating) < 6:
		ratingvalid = True
	if namevalid and townvalid and ratingvalid:
		return True
	else:
		return False
	

def validateReviewDetails(username, comment, stars):
	usernamevalid = False
	commentvalid = False
	starsvalid = False
	if len(username) > 0 and username.isalpha() and len(username) < 80:
		usernamevalid = True
	if len(comment) > 0 and comment.isalpha() and len(comment) < 80:
		commentvalid = True
	if len(stars) > 0 and int(stars) > 0 and int(stars) < 6:
		starsvalid = True
	if usernamevalid and commentvalid and starsvalid:
		return True
	else:
		return False

# ----------------------------------- GET -------------------------------------

@app.route("/api/v1.0/businesses", methods = ["GET"])
def show_all_businesses():
	page_num, page_size = 1, 10
	if request.args.get("pn"):
		page_num = int(request.args.get("pn"))
	if request.args.get("ps"):
		page_size = int(request.args.get("ps"))
	page_start = (page_size * (page_num - 1))
	
	data_to_return = []
	for business in businesses.find().skip(page_start).limit(page_size):
		business["_id"] = str(business["_id"])
		for review in business["reviews"]:
			review["_id"] = str(review["_id"])
		data_to_return.append(business)

	return make_response(jsonify(data_to_return), 200)

@app.route("/api/v1.0/businesses/<string:bid>", methods = ["GET"])
def show_one_business(bid):
	if len(bid) == 24 and all(c in string.hexdigits for c in bid):
		business = businesses.find_one({"_id" : ObjectId(bid)})
		if business is not None:
			business["_id"] = str(business["_id"])
			for review in business["reviews"]:
				review["_id"] = str(review["_id"])
			return make_response(jsonify(business), 200)
		else:
			return make_response(jsonify({"error" : "Invalid business ID"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

@app.route("/api/v1.0/businesses/<string:bid>/reviews", methods = ["GET"])
def fetch_all_reviews(bid):
	if len(bid) == 24 and all(c in string.hexdigits for c in bid):
		if businesses.find_one({"_id" : ObjectId(bid)}):
			page_num, page_size = 1, 10
			if request.args.get("pn"):
				page_num = int(request.args.get("pn"))
			if request.args.get("ps"):
				page_size = int(request.args.get("ps"))
			page_start = (page_size * (page_num - 1))
			data_to_return = []
			business = businesses.find_one({"_id" : ObjectId(bid)}, {"reviews" : 1, "_id" : 0})
			for review in business["reviews"]:
				review["_id"] = str(review["_id"])
				data_to_return.append(review)
			return make_response(jsonify(data_to_return), 200)
		else:
			return make_response(jsonify({"error" : "Invalid business ID"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

@app.route("/api/v1.0/businesses/<string:bid>/reviews/<string:rid>", methods = ["GET"])
def fetch_one_review(bid, rid):
	if len(bid) == 24 and all(c in string.hexdigits for c in bid):
		if len(rid) == 24 and all(c in string.hexdigits for c in rid):
			if businesses.find_one({"_id" : ObjectId(bid)}):
				business = businesses.find_one({"reviews._id" : ObjectId(rid)}, {"_id" : 0, "reviews.$" : 1})
				if business["reviews"][0]["_id"] is not None:
					business["reviews"][0]["_id"] = str(business["reviews"][0]["_id"])
					return make_response(jsonify(business["reviews"][0]), 200)
				else:
					return make_response(jsonify({"error" : "Invalid review ID"}), 404)
			else:
				return make_response(jsonify({"error" : "Invalid business ID"}), 404)
		else:
			return make_response(jsonify({"error" : "Invalid review ID"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

# ----------------------------------- POST ------------------------------------

@app.route("/api/v1.0/businesses", methods = ["POST"])
@jwt_required
def add_business():
	if "name" in request.form and "town" in request.form and "rating" in request.form and validateBusinessDetails(request.form["name"], request.form["town"], request.form["rating"]):
		new_business = {
			"name" : request.form["name"],
			"town" : request.form["town"],
			"rating" : request.form["rating"],
			"reviews" : []
			}
		new_business_id = businesses.insert_one(new_business)
		new_business_link = "http://localhost:5000/api/v1.0/businesses/" + str(new_business_id.inserted_id)
		return make_response(jsonify({"url" : new_business_link}), 201)
	else:
		return make_response(jsonify({"error" : "Missing or invalid form data"}), 404)

@app.route("/api/v1.0/businesses/<string:bid>/reviews", methods = ["POST"])
@jwt_required
def add_new_review(bid):
	if businesses.find_one({"_id" : ObjectId(bid)}):
		if "username" in request.form and "comment" in request.form and "stars" in request.form and validateReviewDetails(request.form["username"], request.form["comment"], request.form["stars"]):
			new_review = {
				"_id" : ObjectId(),
				"username" : request.form["username"],
				"comment" : request.form["comment"],
				"stars" : request.form["stars"]
			}
			businesses.update_one({"_id" : ObjectId(bid) }, {"$push" : {"reviews" : new_review}})
			new_review_link = "http:localhost:5000/api/v1.0/businesses/" + bid + "/reviews/" + str(new_review["_id"])
			return make_response(jsonify({"url" : new_review_link}), 201)
		else:
			return make_response(jsonify({"error" : "Missing or invalid form data"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

# ----------------------------------- PUT -------------------------------------

@app.route("/api/v1.0/businesses/<string:bid>", methods = ["PUT"])
@jwt_required
def edit_business(bid):
	if businesses.find_one({"_id" : ObjectId(bid)}):
		if "name" in request.form:
			if len(request.form["name"]) > 0 and len(request.form["name"]) < 80 and request.form["name"].replace(" ", "").isalnum():
				businesses.update_one({"_id" : ObjectId(bid)}, {"$set" : {"name" : request.form["name"]}})
			else:
				return make_response(jsonify({"error" : "Invalid form data"}), 404)
		if "town" in request.form:
			if len(request.form["town"]) > 0 and len(request.form["town"]) < 80 and request.form["town"].replace(" ", "").isalnum():
				businesses.update_one({"_id" : ObjectId(bid)}, {"$set" : {"town" : request.form["town"]}})
			else:
				return make_response(jsonify({"error" : "Invalid form data"}), 404)	
		if "rating" in request.form:
			if request.form["rating"].isdecimal() and len(request.form["rating"]) > 0 and int(request.form["rating"]) > 0 and int(request.form["rating"]) < 6:
				businesses.update_one({"_id" : ObjectId(bid)}, {"$set" : {"rating" : request.form["rating"]}})
			else:
				return make_response(jsonify({"error" : "Invalid form data"}), 404)
		edited_business_link = "http://localhost:5000/api/v1.0/businesses/" + bid
		return make_response(jsonify({"url" : edited_business_link}), 200)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

@app.route("/api/v1.0/businesses/<string:bid>/reviews/<string:rid>", methods = ["PUT"])
@jwt_required
def edit_review(bid, rid):
	if len(bid) == 24 and all(c in string.hexdigits for c in bid):
		if len(rid) == 24 and all(c in string.hexdigits for c in rid):
			if businesses.find_one({"_id" : ObjectId(bid)}):
				business = businesses.find_one({"reviews._id" : ObjectId(rid)}, {"_id" : 0, "reviews.$" : 1})
				if business["reviews"][0]["_id"] is not None:
					if "username" in request.form:
						if len(request.form["username"]) > 0 and len(request.form["username"]) < 80 and request.form["username"].replace(" ", "").isalnum():
							businesses.update_one({"reviews._id" : ObjectId(rid)}, {"$set" : {"reviews.$.username" : request.form["username"]}})
					if "comment" in request.form:
						if len(request.form["comment"]) > 0 and len(request.form["comment"]) < 80 and request.form["comment"].replace(" ", "").isalnum():
							businesses.update_one({"reviews._id" : ObjectId(rid)}, {"$set" : {"reviews.$.comment" : request.form["comment"]}})
					if "stars" in request.form:
						if request.form["stars"].isdecimal() and len(request.form["stars"]) > 0 and int(request.form["stars"]) > 0 and int(request.form["stars"]) < 6:
							businesses.update_one({"reviews._id" : ObjectId(rid)}, {"$set" : {"reviews.$.stars" : request.form["stars"]}})
					edit_review_url = "http://localhost:5000/api/v1.0/businesses/" + bid + "/reviews/" + rid
					return make_response(jsonify({"url" : edit_review_url}), 200)
				else:
					return make_response(jsonify({"error" : "Invalid review ID"}), 404)
			else:
				return make_response(jsonify({"error" : "Invalid business ID"}), 404)
		else:
			return make_response(jsonify({"error" : "Invalid review ID"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

# ---------------------------------- DELETE -----------------------------------

@app.route("/api/v1.0/businesses/<string:bid>", methods = ["DELETE"])
@jwt_required
def delete_business(bid):
	result = businesses.delete_one({"_id" : ObjectId(bid)})
	if result.deleted_count == 1:
		return make_response(jsonify({}), 204)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

@app.route("/api/v1.0/businesses/<string:bid>/reviews/<string:rid>", methods = ["DELETE"])
@jwt_required
def delete_review(bid, rid):
	if businesses.find_one({"_id" : ObjectId(bid)}):
		business = businesses.find_one({"reviews._id" : ObjectId(rid)}, {"_id" : 0, "reviews.$" : 1})
		if business["reviews"][0]["_id"] is not None:
			businesses.update_one({"_id" : ObjectId(bid)}, { "$pull" : {"reviews" : {"_id" : ObjectId(rid)}}})
			return make_response(jsonify({}), 204)
		else:
			return make_response(jsonify({"error" : "Invalid review ID"}), 404)
	else:
		return make_response(jsonify({"error" : "Invalid business ID"}), 404)

# ----------------------------------- MAIN ------------------------------------

if __name__ == "__main__":
	app.run(debug = True)