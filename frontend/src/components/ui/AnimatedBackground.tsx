export default function AnimatedBackground() {
  const colors = [
    "purple",
    "medium-blue",
    "light-blue",
    "red",
    "orange",
    "yellow",
    "cyan",
    "light-green",
    "lime",
    "magenta",
    "lightish-red",
    "pink",
  ];

  return (
    <div className="particle-bg">
      {colors.map((color) => (
        <div
          key={color}
          className={`particle ${color}`}
        />
      ))}
    </div>
  );
}