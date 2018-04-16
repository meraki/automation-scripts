require 'faraday'
require 'faraday_middleware'
require 'json'

# Define the following vars in your bash/zsh profile
#
# export DASHBOARD_API_KEY='api-key-here'
# export DASHBOARD_API_SHARD_ID='XX'
# export DASHBOARD_API_ORG_ID='X'

dash_api_key  = ENV['DASHBOARD_API_KEY']
dash_org_id   = ENV['DASHBOARD_API_ORG_ID']
dash_shard_id = ENV['DASHBOARD_API_SHARD_ID']


conn = Faraday.new(:url => "https://#{dash_shard_id}.meraki.com") do |faraday|
  faraday.request  :url_encoded
  faraday.response :json
  faraday.adapter  Faraday.default_adapter
end

response = conn.get do |request|
  request.url "api/v0/organizations/#{dash_org_id}/networks"
  request.headers['X-Cisco-Meraki-API-Key'] = "#{dash_api_key}"
  request.headers['Content-Type'] = 'application/json'
end

hash_array = response.body

hash_array.each do |x|
  puts "#{x['id']} :: #{x['name']}"
end