local h = ngx.req.get_headers()
for k, v in pairs(h) do
   if string.sub(k, 1, 15) == 'x-feideconnect-' then
      ngx.log(ngx.ERR, 'clearing header ' .. k .. ': ' .. v)
      ngx.req.clear_header(k)
   end
end

local host = h['host']
local match, err = ngx.re.match(host, '^(.*)\.gk\.feideconnect\.no$')
if not match then
   ngx.log(ngx.ERR, "Bad hostname in request")
   ngx.exit(ngx.HTTP_BAD_REQUEST)
end

local backend = match[1]

local res = ngx.location.capture('/gk/info/' .. backend, {args = {method = ngx.req.get_method()}})

if not (res.status == ngx.HTTP_OK) then
   ngx.exit(res.status)
end

for k, v in pairs(res.header) do
   if string.lower(string.sub(k, 1, 15)) == string.lower('X-FeideConnect-') then
      if string.lower(k) == string.lower('X-FeideConnect-Authorization') then
         ngx.req.set_header('Authorization', v)
      elseif string.lower(k) == string.lower('X-FeideConnect-endpoint') then
            ngx.var.endpoint = v
      else
         ngx.req.set_header(k, v)
      end
   end
end

ngx.log(ngx.ERR, 'got endpoint ' .. ngx.var.endpoint)
