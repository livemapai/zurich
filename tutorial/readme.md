# Map Rendering Technology Workshop

Create yourself a folder called `rendering-workshop` or so. Everything happens in there.

## Task 1: Raster Tiles

Go to https://maplibre.org/maplibre-gl-js/docs/examples/add-a-raster-tile-source/, copy paste the HTML of the example and save it in `index.html`.

Serve the local directory with something like

```
npx http-server . -p 3000 --cors
```

Open the browser and see how it shows the map. In the developer tools ctrl+shift+i look at the network tab and see how it loads the pngs.

Add the current location hash to the url by adding `hash: 'map'` to the maplibre map options.

```diff
        center: [0, 0], // starting position
+       hash: 'map',
        zoom: 0 // starting zoom
```

Show the tile outlines and numbering with `map.showTileBoundaries = true`.

## Task 2: Add Vector Tiles

Add the following source to your stylesheet in the sources object:

```js
'vector-tiles': {
    "url": "https://demotiles.maplibre.org/tiles/tiles.json",
    "type": "vector"
}
```

Now look at the map, nothing has changed yet because we did not add any layers.

Look at https://demotiles.maplibre.org/tiles/tiles.json. You see that the source has multiple "layers". Let's pick the countries layer and show it as a stylesheet layer of type lines. For this add to the layers list this new layer:

```js
{
    'id': 'country-lines',
    'type': 'line',
    'source': 'vector-tiles',
    'source-layer': 'countries',
}
```

Let now use the color `rgb(0, 0, 255)` for the country borders and let's make the lines 5 pixel wide. For this to the country-lines layer the following paint properties:

```
'paint': {
    'line-color': 'rgb(0, 0, 255)',
    'line-width': 5,
}
```

## Task 3: Maputnik

Let's use the style editor Maputnik now. For this first we need a style.json document.

To convert our above style to a json you can simply call `map.getStyle()` in the browser console and save the output in `style.json`.

Now got to https://maplibre.org/maputnik/, click "Open" and load the `style.json` from your computer.

A cool way to see what is actually in your vector tiles is the Maputnik "View->Inspect" feature.

Let's display the country names now. For this add a new layer of type `symbol` choose `vector-source` as the source and `centroids` as the `source-layer`. In "text layout properties" in "Field". "Convert property to data function", Function -> identity, Property -> NAME.

That will produce what is called a data-driven styling expression `["get", "NAME"]`

Expressions in the MapLibre Style Specification have angled braces.

In the Text paint properties you can add a white halo.

Now click "save" and have a look at your style.json file again. It should have this new layer:

```diff
  "layers": [
    {"id": "simple-tiles", "type": "raster", "source": "raster-tiles"},
    {
      "id": "country-lines",
      "type": "line",
      "source": "vector-tiles",
      "source-layer": "countries",
      "paint": {"line-color": "rgb(0, 0, 255)", "line-width": 5}
    },
+    {
+      "id": "labels",
+      "type": "symbol",
+      "source": "vector-tiles",
+      "source-layer": "centroids",
+      "layout": {"text-field": ["get", "NAME"], "text-size": 24},
+      "paint": {
+        "text-halo-color": "rgba(255, 255, 255, 1)",
+        "text-halo-width": 3
+      }
+    }
  ],
```

## Task 4: PMTiles

https://gist.github.com/wipfli/7062a865c89e36fa74b0701289c3c6c8

## Task 5: Planetiler

https://github.com/onthegomap/planetiler-examples
