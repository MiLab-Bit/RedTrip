export type FootprintFeature = {
  type: "Feature";
  properties?: {
    osm_id?: number;
    height_m?: number | null;
    height_schematic?: boolean;
    name?: string | null;
    levels?: string | number | null;
  };
  geometry: {
    type: string;
    coordinates: number[][][];
  };
};
