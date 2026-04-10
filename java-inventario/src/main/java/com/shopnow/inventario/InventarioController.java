package com.shopnow.inventario;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

@RestController
@RequestMapping
public class InventarioController {

    private static final String FILE_NAME = "inventario.csv";
    private static final String[] HEADERS = {"id_producto", "cantidad"};
    private final AuthService authService;

    public InventarioController(AuthService authService) throws IOException {
        this.authService = authService;
        inicializarArchivo();
    }

    @GetMapping("/inventario")
    public List<Map<String, Object>> obtenerInventarioCompleto(
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) throws IOException {
        authService.validateAuthorizationHeader(authorization);
        return leerInventario();
    }

    @GetMapping("/inventario/{id_producto}")
    public ResponseEntity<?> consultarStock(
            @PathVariable int id_producto,
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) throws IOException {
        authService.validateAuthorizationHeader(authorization);
        List<Map<String, Object>> items = leerInventario();
        for (Map<String, Object> item : items) {
            if (((Integer) item.get("id_producto")) == id_producto) {
                return ResponseEntity.ok(item);
            }
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("detail", "Producto no registrado en inventario"));
    }

    @PostMapping("/inventario")
    public ResponseEntity<?> registrarInventario(
            @RequestBody MovimientoInventario mov,
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) throws IOException {
        authService.validateAuthorizationHeader(authorization);
        if (mov.getCantidad() <= 0) {
            return ResponseEntity.badRequest().body(Map.of("detail", "cantidad debe ser mayor a 0"));
        }

        List<Map<String, Object>> items = leerInventario();
        for (Map<String, Object> item : items) {
            if (((Integer) item.get("id_producto")) == mov.getId_producto()) {
                return ResponseEntity.badRequest().body(Map.of("detail", "Producto ya registrado en inventario"));
            }
        }

        items.add(Map.of("id_producto", mov.getId_producto(), "cantidad", mov.getCantidad()));
        guardarInventario(items);

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                "mensaje", "Producto registrado en inventario",
                "id_producto", mov.getId_producto(),
                "cantidad", mov.getCantidad(),
                "status", "success"
        ));
    }

    @PostMapping("/inventario/descontar")
    public ResponseEntity<?> descontarStock(
            @RequestBody MovimientoInventario mov,
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) throws IOException {
        authService.validateAuthorizationHeader(authorization);
        if (mov.getCantidad() <= 0) {
            return ResponseEntity.badRequest().body(Map.of("detail", "cantidad debe ser mayor a 0"));
        }

        List<Map<String, Object>> items = leerInventario();
        for (int i = 0; i < items.size(); i++) {
            Map<String, Object> item = items.get(i);
            if (((Integer) item.get("id_producto")) == mov.getId_producto()) {
                int actual = (Integer) item.get("cantidad");
                if (mov.getCantidad() > actual) {
                    return ResponseEntity.badRequest().body(Map.of("detail", "Inventario insuficiente"));
                }
                Map<String, Object> updated = new LinkedHashMap<>();
                updated.put("id_producto", mov.getId_producto());
                updated.put("cantidad", actual - mov.getCantidad());
                items.set(i, updated);
                guardarInventario(items);
                return ResponseEntity.ok(Map.of(
                        "mensaje", "Inventario descontado exitosamente",
                        "id_producto", mov.getId_producto(),
                        "cantidad_descontada", mov.getCantidad(),
                        "status", "success"
                ));
            }
        }

        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("detail", "Producto no registrado en inventario"));
    }

    @PostMapping("/inventario/agregar")
    public ResponseEntity<?> agregarStock(
            @RequestBody MovimientoInventario mov,
            @RequestHeader(value = "Authorization", required = false) String authorization
    ) throws IOException {
        authService.validateAuthorizationHeader(authorization);
        if (mov.getCantidad() <= 0) {
            return ResponseEntity.badRequest().body(Map.of("detail", "cantidad debe ser mayor a 0"));
        }

        List<Map<String, Object>> items = leerInventario();
        for (int i = 0; i < items.size(); i++) {
            Map<String, Object> item = items.get(i);
            if (((Integer) item.get("id_producto")) == mov.getId_producto()) {
                int actual = (Integer) item.get("cantidad");
                Map<String, Object> updated = new LinkedHashMap<>();
                updated.put("id_producto", mov.getId_producto());
                updated.put("cantidad", actual + mov.getCantidad());
                items.set(i, updated);
                guardarInventario(items);
                return ResponseEntity.ok(Map.of(
                        "mensaje", "Inventario actualizado exitosamente",
                        "id_producto", mov.getId_producto(),
                        "cantidad_agregada", mov.getCantidad(),
                        "status", "success"
                ));
            }
        }

        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("detail", "Producto no registrado en inventario"));
    }

    private void inicializarArchivo() throws IOException {
        Path path = Paths.get(FILE_NAME);
        if (!Files.exists(path)) {
            try (BufferedWriter writer = Files.newBufferedWriter(path)) {
                writer.write(String.join(",", HEADERS));
                writer.newLine();
            }
        }
    }

    private List<Map<String, Object>> leerInventario() throws IOException {
        List<Map<String, Object>> rows = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(FILE_NAME))) {
            String line;
            boolean first = true;
            while ((line = reader.readLine()) != null) {
                if (first) {
                    first = false;
                    continue;
                }
                if (line.isBlank()) continue;
                String[] parts = line.split(",");
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("id_producto", Integer.parseInt(parts[0].trim()));
                row.put("cantidad", Integer.parseInt(parts[1].trim()));
                rows.add(row);
            }
        }
        return rows;
    }

    private void guardarInventario(List<Map<String, Object>> items) throws IOException {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(FILE_NAME))) {
            writer.write(String.join(",", HEADERS));
            writer.newLine();
            for (Map<String, Object> item : items) {
                writer.write(item.get("id_producto") + "," + item.get("cantidad"));
                writer.newLine();
            }
        }
    }
}
