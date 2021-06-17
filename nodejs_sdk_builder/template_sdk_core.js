// /* FILENAME HERE */

const DEFAULT_BASE_URL              = "https://api.meraki.com/api/v1";
const DEFAULT_API_REQUEST_TIMEOUT   = 60000; // milliseconds
const DEFAULT_API_KEY               = "6bec40cf957de430a6f1f2baa056b99a4fac9ea0"; // Sandbox API key

const HTTP_STATUS_NOT_FOUND         = 404;
const HTTP_STATUS_RATE_LIMIT        = 429;

const MAX_RESEND_RETRIES            = 10;
const DEFAULT_BACKOFF_MS            = 5000;

const axios = require('axios');
const querystring = require('querystring');

class MerakiClass {
    constructor(apiKey, baseUrl, timeout) {
        var apiKeyBuffer    = DEFAULT_API_KEY; 
        var baseUrlBuffer   = DEFAULT_BASE_URL;    
        var timeoutBuffer   = DEFAULT_API_REQUEST_TIMEOUT;    

        try {
            if (typeof apiKey != "undefined" && apiKey != null) {
                apiKeyBuffer = apiKey.toString();
            }
                   
            if (typeof baseUrl != "undefined" && baseUrl != null) {
                baseUrlBuffer = baseUrl.toString();
            }
                  
            if (typeof timeout != "undefined" && timeout != null) {
                timeoutBuffer = timeout.toString().parseInt()*1000;
            }            
        }
        catch (error) {
            console.log(error);
        }
    
        this.api = axios.create({
                baseURL: baseUrlBuffer,
                timeout: timeoutBuffer, 
                headers: {"X-Cisco-Meraki-API-Key": apiKeyBuffer}
            });
    }
    
    validateMethod(method) {
        const validMethods = ['get', 'put', 'post', 'delete'];
        var methodIsValid = true;
        try {
            var lowerCaseVerb = method.toString().toLowerCase();            
        }
        catch (error) {
            console.log(error);
            methodIsValid = false;
        }
        
        if (methodIsValid) {
            if (!validMethods.includes(lowerCaseVerb)) {
                console.log("Invalid method: " + lowerCaseVerb);
                methodIsValid = false;                    
            }
        }
        return methodIsValid;
    }
    
    request(self, method, endpoint, config, retry) { 
        
        return new Promise(function (resolve, reject) {
            
            var methodIsValid = self.validateMethod(method);
            
            if (!methodIsValid) {
                reject({errors: ["Invalid method"]});
            }
            else {                
                var retryNumber = 0;
                if (typeof retry == "number") {
                    retryNumber = retry;
                }
                
                // for retries, etc
                var dataOnlyConfig = null;
                
                var axiosConfig = {
                    url: endpoint,
                    method: method.toString().toLowerCase()
                };
                
                if (typeof config != "undefined" && config != null) {
                    if ("query" in config && config.query != null) {                    
                        axiosConfig.url = axiosConfig.url + "?" + querystring.stringify(config['query']);
                    }
                    
                    if ("data" in config && config.data != null) {
                        axiosConfig.data = config.data;
                        
                        // for retries, etc
                        dataOnlyConfig = {data: config.data};
                    }
                }
                                
                var returnValues = {
                    success: false,
                    status: HTTP_STATUS_NOT_FOUND,
                    data: null,
                    errors: null
                };
                
                console.log(method.toString().toUpperCase() + " " + axiosConfig.url);
                
                self.api(axiosConfig)
                    .then(function(response) {                        
                        if("link" in response.request.res.headers) {
                            var nextPageNotFound = true;
                            var linkRecord = response.request.res.headers.link.split(", ");
                            for (var i = 0; i < linkRecord.length; i++) {
                                var splitRecord = linkRecord[i].split("; ");
                                if (splitRecord[1] == "rel=next") {
                                    nextPageNotFound = false;
                                    
                                    var nextUrl = splitRecord[0].substring(1, splitRecord[0].length-1);                                    
                                    var nextEndpoint = nextUrl.split("meraki.com/api/v1")[1];
                                                                        
                                    self.request(self, axiosConfig.method, nextEndpoint, dataOnlyConfig, 0)
                                        .then(function(nextResponse) {
                                            var combined = [];
                                            
                                            for (var i in response.data) {
                                                combined.push(response.data[i]);
                                            };
                                            
                                            for (var j in nextResponse.data) {
                                                combined.push(nextResponse.data[j]);
                                            };
                                            
                                            returnValues.success = true;
                                            returnValues.status = nextResponse.status;
                                            returnValues.data = combined;
                                            
                                            resolve(returnValues);   
                                        })
                                        .catch(function(error) {
                                            if ("status" in error) {
                                                returnValues.status = error.status;                                
                                            }
                                            if ("errors" in error) {
                                                returnValues.errors = error.errors;                                
                                            }
                                            reject(returnValues);                                         
                                        });
                                        
                                    break;
                                }         
                            }
                            
                            if (nextPageNotFound) {
                                // this is the FINAL response page
                                returnValues.success = true;
                                returnValues.status = response.request.res.statusCode;
                                returnValues.data = response.data;    
                                resolve(returnValues);
                            }
                        }
                        else {
                            // this is the ONLY response page
                            returnValues.success = true;
                            returnValues.status = response.request.res.statusCode;
                            returnValues.data = response.data;                            
                            resolve(returnValues);                         
                        }
                    })
                    .catch(function(error) {                        
                        if ("response" in error && "status" in error.response && error.response.status == HTTP_STATUS_RATE_LIMIT) {
                            // Hit rate limiter, retry if able
                            
                            retryNumber += 1;
                            if (retryNumber <= MAX_RESEND_RETRIES) {
                                // Still have retries left, back off and resend
                                
                                // https://www.geeksforgeeks.org/how-to-wait-for-a-promise-to-finish-before-returning-the-variable-of-a-function/
                                const wait=ms=>new Promise(resolve => setTimeout(resolve, ms));
                                
                                var backOffTimerMs = DEFAULT_BACKOFF_MS;
                                
                                if ( "retry-after" in error.response.headers) {
                                    backOffTimerMs = error.response.headers["retry-after"]*1000;
                                }
                                console.log("request: Hit API rate limit. Waiting " + backOffTimerMs + "ms before retry");
                                
                                wait(backOffTimerMs).then(() => {
                                    self.request(self, axiosConfig.method, axiosConfig.url, dataOnlyConfig, retryNumber+1)
                                        .then(function(retryResponse){
                                            // Yay, this time it went through. Use response as own response                                            
                                            returnValues.success = true;
                                            returnValues.status = retryResponse.status;
                                            returnValues.data = retryResponse.data;                            
                                            resolve(returnValues); 
                                            
                                        })
                                        .catch(function(retryError){
                                            // Request unsuccessful. Either out of retries or general error. Fail
                                            returnValues.status = retryError.status;
                                            returnValues.errors = retryError.errors;
                                            reject(returnValues);                                            
                                        });
                                }).catch(() => {
                                    console.log("request: Retry wait failed");
                                });                                
                            } else {
                                // Hit max retries, give up
                                returnValues.status = HTTP_STATUS_RATE_LIMIT;
                                returnValues.errors = ["API busy. Max retries reached"];
                                reject(returnValues);    
                            }
                            
                        } else {
                            // Did not hit rate limiter, this is some other error. Do not retry, just fail
                            if ("response" in error) {                                
                                if ("data" in error.response && "errors" in error.response.data) {    
                                    returnValues.errors = error.response.data.errors;                                
                                }        
                                if ("status" in error.response) {
                                    returnValues.status = error.response.status;                                
                                }                        
                            }
                            reject(returnValues);
                        }
                    });                                
            }
        });
    }
    
    
/* ENDPOINTS HERE */
    
} // class MerakiClass

var Meraki = new MerakiClass();

module.exports = Meraki;
module.exports.MerakiClass = MerakiClass;