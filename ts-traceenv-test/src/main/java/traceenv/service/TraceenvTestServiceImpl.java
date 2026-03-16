package traceenv.service;

import edu.fudan.common.util.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class TraceenvTestServiceImpl implements TraceenvTestService {

    @Autowired
    private RestTemplate restTemplate;

    private static final Logger LOGGER = LoggerFactory.getLogger(TraceenvTestServiceImpl.class);

    private String getServiceUrl(String serviceName) {
        return "http://" + serviceName;
    }

    @Override
    public Response test(HttpHeaders headers) {
        return new Response<>(1, "IS yyl big D", null);
    }

    @Override
    public Response callOrderService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-order-service", "/api/v1/orderservice/traceenv", headers);
    }

    @Override
    public Response callPreserveService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-preserve-service", "/api/v1/preserveservice/traceenv", headers);
    }

    @Override
    public Response callPreserveOtherService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-preserve-other-service", "/api/v1/preserveotherservice/traceenv", headers);
    }

    @Override
    public Response callTrainService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-train-service", "/api/v1/trainservice/traceenv", headers);
    }

    @Override
    public Response callTravelService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-travel-service", "/api/v1/travelservice/traceenv", headers);
    }

    @Override
    public Response callPaymentService(HttpHeaders headers) {
        return callRemoteTraceenv("ts-payment-service", "/api/v1/paymentservice/traceenv", headers);
    }

    @Override
    public Response callAll(HttpHeaders headers) {
        Map<String, String> results = new LinkedHashMap<>();

        String[][] services = {
                {"ts-order-service", "/api/v1/orderservice/traceenv"},
                {"ts-preserve-service", "/api/v1/preserveservice/traceenv"},
                {"ts-preserve-other-service", "/api/v1/preserveotherservice/traceenv"},
                {"ts-train-service", "/api/v1/trainservice/traceenv"},
                {"ts-travel-service", "/api/v1/travelservice/traceenv"},
                {"ts-payment-service", "/api/v1/paymentservice/traceenv"},
        };

        for (String[] svc : services) {
            try {
                Response resp = callRemoteTraceenv(svc[0], svc[1], headers);
                results.put(svc[0], resp.getMsg());
            } catch (Exception e) {
                LOGGER.warn("[callAll][Call {} failed][message: {}]", svc[0], e.getMessage());
                results.put(svc[0], "FAILED: " + e.getMessage());
            }
        }

        return new Response<>(1, "Call all services complete", results);
    }

    private Response callRemoteTraceenv(String serviceName, String path, HttpHeaders headers) {
        String url = getServiceUrl(serviceName);
        HttpEntity requestEntity = new HttpEntity(headers);
        ResponseEntity<Response<String>> response = restTemplate.exchange(
                url + path,
                HttpMethod.GET,
                requestEntity,
                new ParameterizedTypeReference<Response<String>>() {});
        LOGGER.info("[callRemoteTraceenv][Call {} success]", serviceName);
        return response.getBody();
    }
}
