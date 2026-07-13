/** Small indeterminate spinner matching the prototype's ng-spin ring. */
export function Spinner({
  size = 18,
  color = "#161616",
  track = "#e2e2dc",
  thickness = 2,
}: {
  size?: number;
  color?: string;
  track?: string;
  thickness?: number;
}) {
  return (
    <span
      style={{
        width: size,
        height: size,
        border: `${thickness}px solid ${track}`,
        borderTopColor: color,
        borderRadius: "50%",
        display: "inline-block",
        animation: "ng-spin .7s linear infinite",
      }}
    />
  );
}
